from __future__ import annotations

import secrets
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from time import time
from typing import Any, Literal, ParamSpec, TypedDict, TypeVar, cast
from uuid import uuid4

from flask import Blueprint, Request, abort, redirect, render_template, request, session, url_for
from flask.typing import ResponseReturnValue

from app.arena import Arena
from app.classes import CLASS_REGISTRY, UnitClass, get_unit_class, register_unit_class
from app.equipment import (
    SHIELD_REGISTRY,
    WEAPON_REGISTRY,
    get_shield,
    get_weapon,
    load_equipment_from_json,
)
from app.stats import SessionStats, bump, dump, load_from
from app.unit import AIUnit, PlayerUnit, create_ai, create_player

bp = Blueprint(
    "web",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)

_ARENAS: dict[str, tuple[Arena, float]] = {}
_ARENA_TTL = 30 * 60
_ARENA_MAX = 1000


def _result_of(arena: Arena) -> str | None:
    if not arena.is_finished:
        return None
    player_alive = arena.player.hull > 0
    enemy_alive = arena.ai.hull > 0
    if player_alive and not enemy_alive:
        return "win"
    if enemy_alive and not player_alive:
        return "loss"
    return "draw"


def _update_stats_if_finished(arena: Arena) -> None:
    res = _result_of(arena)
    if res is None:
        return
    stats = load_from(session.get("stats"))
    session["stats"] = dump(bump(stats, res))
    session.modified = True


class Selection(TypedDict):
    name: str
    unit_class: str
    weapon: str
    shield: str


# ----------------- хелперы.
@bp.get("/")
def index() -> ResponseReturnValue:
    return redirect(url_for("web.choose_hero_form"))


@bp.get("/quick-fight")
def quick_fight() -> ResponseReturnValue:
    _set_session_arena(_new_default_arena())
    return redirect(url_for("web.fight"))


@bp.get("/choose-hero/quick-fight")
def quick_fight_alias() -> ResponseReturnValue:
    return redirect(url_for("web.quick_fight"))


@bp.get("/favicon.ico")
def favicon() -> ResponseReturnValue:
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
        "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
        "<stop offset='0' stop-color='#6cf'/><stop offset='1' stop-color='#39f'/>"
        "</linearGradient></defs>"
        "<polygon points='32,4 44,28 32,24 20,28' fill='url(#g)'/>"
        "<rect x='30' y='24' width='4' height='20' fill='#9cf'/>"
        "<polygon points='32,44 40,60 24,60' fill='#9cf'/>"
        "</svg>"
    )
    return svg, 200, {"Content-Type": "image/svg+xml"}


def _load_equipment_if_needed() -> None:
    """Загрузка equipment.json в реестры"""
    if WEAPON_REGISTRY and SHIELD_REGISTRY:
        return
    json_path = Path("equipment.json")
    if not json_path.exists():
        raise RuntimeError("equipment.json не найден в корне.")
    load_equipment_from_json(str(json_path))


def _ensure_sample_classes() -> None:
    """Регеистрация двух новых классов если их нет в реестре."""
    if "interceptor" not in CLASS_REGISTRY:
        register_unit_class(
            "interceptor",
            UnitClass(
                name="Interceptor",
                hull_max=40,
                energy_max=25,
                shield_mod=1.1,
                attack_mod=1.0,
            ),
        )
    if "destroyer" not in CLASS_REGISTRY:
        register_unit_class(
            "destroyer",
            UnitClass(
                name="Destroyer",
                hull_max=55,
                energy_max=20,
                shield_mod=0.9,
                attack_mod=1.2,
            ),
        )


def _gc_arenas() -> None:
    now = time()
    # удалить по TTL
    for aid, (_, ts) in list(_ARENAS.items()):
        if now - ts > _ARENA_TTL:
            _ARENAS.pop(aid, None)
    # если всё еще много — подрежем самых старых
    if len(_ARENAS) > _ARENA_MAX:
        oldest = sorted(_ARENAS.items(), key=lambda kv: kv[1][1])[: len(_ARENAS) - _ARENA_MAX]
        for aid, _ in oldest:
            _ARENAS.pop(aid, None)


def _touch(aid: str) -> None:
    arena, _ = _ARENAS[aid]
    _ARENAS[aid] = (arena, time())


def _new_default_arena() -> Arena:
    _load_equipment_if_needed()
    _ensure_sample_classes()
    p_class = get_unit_class("interceptor")
    e_class = get_unit_class("destroyer")

    try:
        w_def = get_weapon("railgun_mk1")
    except KeyError:
        w_def = next(iter(WEAPON_REGISTRY.values()))  # любой доступный

    try:
        s_def = get_shield("shield_heavy")
    except KeyError:
        s_def = next(iter(SHIELD_REGISTRY.values()))  # любой доступный

    player = create_player(
        name="Alpha",
        unit_class=p_class,
        weapon=w_def,
        shield=s_def,
    )
    enemy = create_ai(
        name="Omega",
        unit_class=e_class,
        weapon=w_def,
        shield=s_def,
    )

    arena = Arena()
    arena.start(player=player, ai=enemy)
    return arena


def _set_session_arena(arena: Arena) -> Arena:
    _gc_arenas()
    aid = str(uuid4())
    session["arena_id"] = aid
    _ARENAS[aid] = (arena, time())
    return arena


def _get_session_arena() -> Arena:
    """Вернуть арену из карты по session['arena_id']; создать дефолтную при отсутствии."""
    _gc_arenas()
    aid = session.get("arena_id")
    if isinstance(aid, str) and aid in _ARENAS:
        arena, _ts = _ARENAS[aid]
        # страхуемся: в редком случае арена есть, но не стартовала
        if not arena.is_initialized:
            arena = _new_default_arena()
            _ARENAS[aid] = (arena, time())
        else:
            _touch(aid)
        return arena

    return _set_session_arena(_new_default_arena())


def _ensure_default_battle() -> Arena:
    """Если бой не инициализирован поднимаем дефолт."""
    _load_equipment_if_needed()
    _ensure_sample_classes()

    arena = Arena()

    if arena.is_initialized:
        return arena

    p_class = get_unit_class("interceptor")
    e_class = get_unit_class("destroyer")

    try:
        w_def = get_weapon("railgun_mk1")
    except KeyError:
        w_def = next(iter(WEAPON_REGISTRY.values()))  # любой доступный

    try:
        s_def = get_shield("shield_heavy")
    except KeyError:
        s_def = next(iter(SHIELD_REGISTRY.values()))  # любой доступный

    player = create_player(
        name="Alpha",
        unit_class=p_class,
        weapon=w_def,
        shield=s_def,
    )
    enemy = create_ai(
        name="Omega",
        unit_class=e_class,
        weapon=w_def,
        shield=s_def,
    )
    arena.start(player=player, ai=enemy)
    return arena


def _is_htmx(req: Request) -> bool:
    """Возвращает True, если запрос пришел от HTMX."""
    return req.headers.get("HX-Request") == "true"


def _ensure_csrf_token() -> str:
    """Создает или возвращает CSRF-токен."""
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_hex(16)
        session["_csrf_token"] = token
    return str(token)


def _auto_ai(arena: Arena) -> None:
    for _ in range(8):
        if arena.is_finished or arena.turn == "player":
            break
        arena._ai_take_turn()


@bp.app_context_processor
def _inject_csrf() -> dict[str, str]:
    """Делает csrf_token доступным в джинже как переменную."""
    return {"csrf_token": _ensure_csrf_token()}


P = ParamSpec("P")
R = TypeVar("R")


def require_csrf(view: Callable[P, R]) -> Callable[P, R]:  # noqa: UP047
    @wraps(view)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        sent = request.headers.get("X-CSRF-Token") or request.headers.get("X-CSRF-TOKEN") or ""
        expected = session.get("_csrf_token")
        if sent != expected:
            abort(400)
        return view(*args, **kwargs)

    return wrapped


def _render_fight(arena: Arena) -> ResponseReturnValue:
    """
    Универсальный рендер боя:
    если HTMX: отдать только панель боя (partial),
    иначе: полную страницу.
    """
    stats_dict = dump(load_from(session.get("stats")))
    if _is_htmx(request):
        return render_template("partials/fight_panel.html", arena=arena, stats=stats_dict)
    return render_template("fight.html", arena=arena, stats=stats_dict)


def _build_player_from_selection(sel: Selection) -> PlayerUnit:
    """Сборка PlayerUnit."""
    return create_player(
        name=sel["name"],
        unit_class=get_unit_class(sel["unit_class"]),
        weapon=get_weapon(sel["weapon"]),
        shield=get_shield(sel["shield"]),
    )


def _build_ai_from_selection(sel: Selection) -> AIUnit:
    """Сборка AIUnit."""
    return create_ai(
        name=sel["name"],
        unit_class=get_unit_class(sel["unit_class"]),
        weapon=get_weapon(sel["weapon"]),
        shield=get_shield(sel["shield"]),
    )


@bp.get("/fight")
def fight() -> ResponseReturnValue:
    arena = _get_session_arena()
    return _render_fight(arena)


@bp.post("/fight/hit")
@require_csrf
def fight_hit() -> ResponseReturnValue:
    """Ход игрока."""
    arena = _get_session_arena()
    if not arena.is_finished and arena.turn == "player":
        arena.attack()
        _auto_ai(arena)
    _update_stats_if_finished(arena)
    return _render_fight(arena)


@bp.post("/fight/pass-turn")
@require_csrf
def fight_pass() -> ResponseReturnValue:
    """Пропуск хода игроком."""
    arena = _get_session_arena()
    if not arena.is_finished and arena.turn == "player":
        arena.pass_turn()
        _auto_ai(arena)
    _update_stats_if_finished(arena)
    return _render_fight(arena)


@bp.post("/fight/end-fight")
@require_csrf
def fight_end() -> ResponseReturnValue:
    """Сброс боя"""
    arena = _set_session_arena(_new_default_arena())
    return _render_fight(arena)


@bp.post("/stats/reset")
@require_csrf
def reset_stats() -> ResponseReturnValue:
    session["stats"] = dump(SessionStats())
    session.modified = True
    if _is_htmx(request):
        return render_template("_stats_box.html", stats=session["stats"])
    return redirect(url_for("web.fight"))


@bp.post("/fight/use-skill/<slug>")
@require_csrf
def fight_use_skill(slug: str) -> ResponseReturnValue:
    """Ход игрока с применением скилла."""
    arena = _get_session_arena()
    if not arena.is_finished and arena.turn == "player" and slug in {"overcharge", "emp"}:
        arena.attack_with_player_skill(slug)
        _auto_ai(arena)
    _update_stats_if_finished(arena)
    return _render_fight(arena)


@bp.get("/choose-hero", endpoint="choose_hero_form")
def choose_hero_from() -> ResponseReturnValue:
    """Показываем форму выбора героя"""

    _load_equipment_if_needed()
    _ensure_sample_classes()

    sel: dict[str, Any] = cast(dict[str, Any] | None, session.get("hero_selection")) or {}
    selected_class = sel.get("unit_class", "")
    selected_weapon = sel.get("weapon", "")
    selected_shield = sel.get("shield", "")
    selected_name = sel.get("name", "")

    return render_template(
        "choose_hero.html",
        classes=CLASS_REGISTRY,
        weapons=WEAPON_REGISTRY,
        shields=SHIELD_REGISTRY,
        selected_class=selected_class,
        selected_weapon=selected_weapon,
        selected_shield=selected_shield,
        selected_name=selected_name,
    )


@bp.post("/choose-hero")
def choose_hero_submit() -> ResponseReturnValue:
    _load_equipment_if_needed()
    _ensure_sample_classes()

    unit_class_slug = request.form.get("unit_class", "")
    weapon_slug = request.form.get("weapon", "")
    shield_slug = request.form.get("shield", "")
    name = request.form.get("name", "").strip() or "Player"

    if unit_class_slug not in CLASS_REGISTRY:
        return "Unknown unit_class", 400
    if weapon_slug not in WEAPON_REGISTRY:
        return "Unknown weapon", 400
    if shield_slug not in SHIELD_REGISTRY:
        return "Unknown shield", 400

    session["hero_selection"] = {
        "name": name,
        "unit_class": unit_class_slug,
        "weapon": weapon_slug,
        "shield": shield_slug,
    }

    return redirect(url_for("web.choose_enemy_form"))


@bp.get("/choose-enemy", endpoint="choose_enemy_form")
def choose_enemy_from() -> ResponseReturnValue:
    """Форма выбора врага."""
    _load_equipment_if_needed()
    _ensure_sample_classes()

    if "hero_selection" not in session:
        return redirect(url_for("web.choose_hero_form"))

    sel: dict[str, Any] = cast(dict[str, Any] | None, session.get("enemy_selection")) or {}
    selected_class = sel.get("unit_class", "")
    selected_weapon = sel.get("weapon", "")
    selected_shield = sel.get("shield", "")
    selected_name = sel.get("name", "")
    selected_difficulty = cast(str, session.get("difficulty", "normal"))

    return render_template(
        "choose_enemy.html",
        classes=CLASS_REGISTRY,
        weapons=WEAPON_REGISTRY,
        shields=SHIELD_REGISTRY,
        selected_class=selected_class,
        selected_weapon=selected_weapon,
        selected_shield=selected_shield,
        selected_name=selected_name,
        selected_difficulty=selected_difficulty,
    )


@bp.post("/choose-enemy", endpoint="choose_enemy_submit")
def choose_enemy_submit() -> ResponseReturnValue:
    """Сохраняем выбор врага и уводим на старт боя."""

    _load_equipment_if_needed()
    _ensure_sample_classes()

    unit_class_slug = request.form.get("unit_class", "")
    weapon_slug = request.form.get("weapon", "")
    shield_slug = request.form.get("shield", "")
    name = request.form.get("name", "").strip() or "Enemy"
    difficulty = request.form.get("difficulty", "normal").strip().lower()
    if difficulty not in {"normal", "easy", "hard"}:
        difficulty = "normal"

    if unit_class_slug not in CLASS_REGISTRY:
        return "Unknown unit_class", 400
    if weapon_slug not in WEAPON_REGISTRY:
        return "Unknown weapon", 400
    if shield_slug not in SHIELD_REGISTRY:
        return "Unknown shield", 400

    session["enemy_selection"] = {
        "name": name,
        "unit_class": unit_class_slug,
        "weapon": weapon_slug,
        "shield": shield_slug,
    }
    session["difficulty"] = difficulty

    return redirect(url_for("web.start_fight"))


@bp.route("/start-fight", methods=["GET", "POST"])
def start_fight() -> ResponseReturnValue:
    _load_equipment_if_needed()
    _ensure_sample_classes()

    hero_raw = session.get("hero_selection")
    enemy_raw = session.get("enemy_selection")

    if hero_raw is None:
        return redirect(url_for("web.choose_hero_form"))
    if enemy_raw is None:
        return redirect(url_for("web.choose_enemy_form"))

    hero: Selection = cast(Selection, hero_raw)
    enemy: Selection = cast(Selection, enemy_raw)

    player = _build_player_from_selection(hero)
    ai = _build_ai_from_selection(enemy)

    arena = Arena()

    raw_diff = cast(str, session.get("difficulty", "normal")).lower()
    if raw_diff == "easy":
        diff_lit: Literal["easy", "normal", "hard"] = "easy"
    elif raw_diff == "hard":
        diff_lit = "hard"
    else:
        diff_lit = "normal"

    arena.start(player=player, ai=ai, difficulty=diff_lit)

    _set_session_arena(arena)
    return redirect(url_for("web.fight"))


@bp.get("/healthz")
def healthz() -> str:
    return "oK"
