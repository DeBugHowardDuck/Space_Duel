from __future__ import annotations

import secrets
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import ParamSpec, TypedDict, TypeVar, cast

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
from app.unit import AIUnit, PlayerUnit, create_ai, create_player

bp = Blueprint(
    "web",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)


class Selection(TypedDict):
    name: str
    unit_class: str
    weapon: str
    shield: str


# ----------------- хелперы.
@bp.get("/")
def index() -> ResponseReturnValue:
    return "Space Duel: сервис поднят"


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


def _ensure_default_battle() -> Arena:
    """Если бой не инициализирован поднимаем дефолт."""
    _load_equipment_if_needed()
    _ensure_sample_classes()

    arena = Arena()

    if arena.is_initialized:
        return arena

    p_class = get_unit_class("interceptor")
    e_class = get_unit_class("destroyer")

    player = create_player(
        name="Alpha",
        unit_class=p_class,
        weapon=get_weapon("railgun_mk1"),
        shield=get_shield("shield_heavy"),
    )

    enemy = create_ai(
        name="Omega",
        unit_class=e_class,
        weapon=get_weapon("railgun_mk1"),
        shield=get_shield("shield_heavy"),
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
    if _is_htmx(request):
        return render_template("partials/fight_panel.html", arena=arena)
    return render_template("fight.html", arena=arena)


# def _render_state(arena: Arena) -> str:
#     """Вывод состояния боя."""
#     p = arena.player
#     e = arena.ai
#     lines: list[str] = [
#         "=== SPACE DUEL ===",
#         f"Ход: {arena.turn}",
#         "",
#         f"PLAYER {p.name}: hull={p.hull}/{p.hull_max}  "
#         f"shield={p.shield_hp}/{p.shield.capacity}  "
#         f"energy={p.energy}/{p.energy_max}",
#         f"ENEMY  {e.name}: hull={e.hull}/{e.hull_max}  "
#         f"shield={e.shield_hp}/{e.shield.capacity}  "
#         f"energy={e.energy}/{e.energy_max}",
#         "",
#         "Последние события:",
#     ]
#     lines.extend(f"- {line}" for line in arena.log[-5:])
#     lines.append("")
#     lines.append("Доступные действия:")
#     lines.append("GET /fight/hit            - удар")
#     lines.append("GET /fight/pass-turn      - пропуск")
#     lines.append("GET /fight/end-fight      - завершить бой (сброс)")
#     return "\n".join(lines)


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
    arena = _ensure_default_battle()
    return _render_fight(arena)


@bp.post("/fight/hit")
@require_csrf
def fight_hit() -> ResponseReturnValue:
    """Ход игрока (POST, CSRF)."""
    arena = _ensure_default_battle()
    if not arena.is_finished and arena.turn == "player":
        arena.attack()
    return _render_fight(arena)


@bp.post("/fight/pass-turn")
@require_csrf
def fight_pass() -> ResponseReturnValue:
    """Пропуск хода игроком (накапливаем энергию/щит)."""
    arena = _ensure_default_battle()
    if not arena.is_finished and arena.turn == "player":
        arena.pass_turn()
    return _render_fight(arena)


@bp.post("/fight/end-fight")
@require_csrf
def fight_end() -> ResponseReturnValue:
    """Сброс боя"""
    arena = Arena()
    if arena.is_initialized:
        arena.reset()
    arena = _ensure_default_battle()
    return _render_fight(arena)


@bp.get("/choose-hero", endpoint="choose_hero_form")
def choose_hero_from() -> ResponseReturnValue:
    """Показываем форму выбора героя"""
    _load_equipment_if_needed()
    _ensure_sample_classes()
    return render_template(
        "choose_hero.html",
        classes=CLASS_REGISTRY,
        weapons=WEAPON_REGISTRY,
        shields=SHIELD_REGISTRY,
    )


@bp.post("/choose-hero")
def choose_hero_submit() -> ResponseReturnValue:
    unit_class_slug = request.form.get("unit_class", "")
    weapon_slug = request.form.get("weapon", "")
    shield_slug = request.form.get("shield", "")
    name = request.form.get("name", "").strip() or "Player"
    # Достаём поля из формы; name обрезаем и подставляем дефолт

    # Базовая валидация: все слаги должны существовать в реестрах.
    if unit_class_slug not in CLASS_REGISTRY:
        return "Unknown unit_class", 400
    if weapon_slug not in WEAPON_REGISTRY:
        return "Unknown weapon", 400
    if shield_slug not in SHIELD_REGISTRY:
        return "Unknown shield", 400

    # Сохраняем выбор в сессии
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

    return render_template(
        "choose_enemy.html",
        classes=CLASS_REGISTRY,
        weapons=WEAPON_REGISTRY,
        shields=SHIELD_REGISTRY,
    )


@bp.post("/choose-enemy", endpoint="choose_enemy_submit")
def choose_enemy_submit() -> ResponseReturnValue:
    """Сохраняем выбор врага и уводим на старт боя."""
    unit_class_slug = request.form.get("unit_class", "")
    weapon_slug = request.form.get("weapon", "")
    shield_slug = request.form.get("shield", "")
    name = request.form.get("name", "").strip() or "Enemy"

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

    arena = Arena()
    player = _build_player_from_selection(hero)
    ai = _build_ai_from_selection(enemy)
    arena.start(player=player, ai=ai)

    return redirect(url_for("web.fight"))


@bp.post("/fight/use-skill/<slug>")
@require_csrf
def fight_use_skill(slug: str) -> ResponseReturnValue:
    """Ход игрока с применением скилла."""
    arena = _ensure_default_battle()
    # Никаких текстовых ответов — только обновление панели.
    if not arena.is_finished and arena.turn == "player" and slug in {"overcharge", "emp"}:
        arena.attack_with_player_skill(slug)
    return _render_fight(arena)


@bp.get("/healthz")
def healthz() -> str:
    return "oK"
