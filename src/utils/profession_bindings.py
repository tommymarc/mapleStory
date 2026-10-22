"""Runtime helpers for profession-labelled keyboard bindings."""

import copy
import re

BUFF_SLOT_RE = re.compile(r"^buff(\d+)$")


RUNTIME_CONFIG_KEY = "profession"

LEGACY_ACTION_KEY_MAP = {
    "jump": "jump",
    "x_axis_movement": "teleport",
    "add_hp": "add_hp",
    "add_mp": "add_mp",
}

# Sections a profession `overrides` block may deep-merge into the live cfg.
# reset_profession_overrides restores these from fallback when switching away.
OVERRIDE_SECTIONS = (
    "directional_attack",
    "hybrid_attack",
    "aoe_skill",
    "monster_detect",
    "combat",
)


def _deep_update(dst, src):
    """In-place deep merge; `src` wins on conflicts."""
    if not isinstance(dst, dict) or not isinstance(src, dict):
        return
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _deep_update(dst[key], value)
        else:
            dst[key] = copy.deepcopy(value)


def reset_profession_overrides(cfg, fallback_cfg):
    """Restore profession-controlled values from the fallback config."""
    if not isinstance(fallback_cfg, dict):
        cfg.pop(RUNTIME_CONFIG_KEY, None)
        return

    fallback_bot = fallback_cfg.get("bot", {})
    fallback_keys = fallback_cfg.get("key", {})
    fallback_buff = fallback_cfg.get("buff_skill", {})

    if "attack" in fallback_bot:
        cfg["bot"]["attack"] = fallback_bot["attack"]
    if "jump_attack" in fallback_bot:
        cfg["bot"]["jump_attack"] = fallback_bot["jump_attack"]
    if "jump_attack_delay_min" in fallback_bot:
        cfg["bot"]["jump_attack_delay_min"] = fallback_bot["jump_attack_delay_min"]
    if "jump_attack_delay_max" in fallback_bot:
        cfg["bot"]["jump_attack_delay_max"] = fallback_bot["jump_attack_delay_max"]
    for key_name in (
        "aoe_skill",
        "directional_attack",
        "teleport",
        "jump",
        "add_hp",
        "add_mp",
    ):
        if key_name in fallback_keys:
            cfg["key"][key_name] = fallback_keys[key_name]
    if "keys" in fallback_buff:
        cfg["buff_skill"]["keys"] = copy.deepcopy(fallback_buff["keys"])
    if "cooldown" in fallback_buff:
        cfg["buff_skill"]["cooldown"] = copy.deepcopy(fallback_buff["cooldown"])

    # Restore engine tuning sections that profession overrides may have changed.
    for section in OVERRIDE_SECTIONS:
        if section in fallback_cfg:
            cfg[section] = copy.deepcopy(fallback_cfg[section])

    cfg.pop(RUNTIME_CONFIG_KEY, None)


def collect_buff_skill_slots(bindings, intervals):
    """Return ordered (function_id, key, cooldown) for buff, buff1, buff2, ..."""
    if not isinstance(bindings, dict):
        bindings = {}
    if not isinstance(intervals, dict):
        intervals = {}
    slots = []
    seen_keys = set()

    def add(function_id):
        key = bindings.get(function_id, "")
        if not key or key in seen_keys:
            return
        seen_keys.add(key)
        if function_id == "buff":
            cooldown = intervals.get("buff", intervals.get("buff_pet_food", 60))
        else:
            cooldown = intervals.get(function_id, 60)
        try:
            cooldown = int(cooldown)
        except (TypeError, ValueError):
            cooldown = 60
        slots.append((function_id, key, max(1, cooldown)))

    add("buff")
    numbered = []
    for function_id in bindings:
        match = BUFF_SLOT_RE.fullmatch(str(function_id))
        if match:
            numbered.append((int(match.group(1)), str(function_id)))
    for _, function_id in sorted(numbered):
        add(function_id)
    return slots


def apply_profession_profile(cfg, name, profile, fallback_cfg=None):
    """Apply one profession profile to both the semantic and legacy configs."""
    if fallback_cfg is not None:
        reset_profession_overrides(cfg, fallback_cfg)
    has_profile = isinstance(profile, dict) and bool(profile)
    if not isinstance(profile, dict):
        profile = {}

    bindings = profile.get("bindings", {})
    intervals = profile.get("intervals", {})
    if not isinstance(bindings, dict):
        bindings = {}
    if not isinstance(intervals, dict):
        intervals = {}

    attack_type = profile.get("main_attack_type", "directional")
    if attack_type not in ("directional", "aoe_skill", "hybrid"):
        attack_type = "directional"

    # Keep every labelled binding in the runtime config. Other modules can
    # resolve actions such as "secondary_attack_1" without knowing YAML paths.
    jump_attack = bool(profile.get("jump_attack", False))

    overrides = profile.get("overrides", {})
    if not isinstance(overrides, dict):
        overrides = {}

    cfg[RUNTIME_CONFIG_KEY] = {
        "name": name,
        "main_attack_type": attack_type,
        "jump_attack": jump_attack,
        "bindings": copy.deepcopy(bindings),
        "intervals": copy.deepcopy(intervals),
        "overrides": copy.deepcopy(overrides),
    }

    # Legacy engine compatibility for the actions it already understands.
    if has_profile:
        cfg["bot"]["attack"] = attack_type
        cfg["bot"]["jump_attack"] = jump_attack
    main_attack_key = bindings.get("main_attack", "")
    aoe_attack_key = bindings.get("aoe_attack", "")
    if attack_type == "aoe_skill":
        if aoe_attack_key or main_attack_key:
            cfg["key"]["aoe_skill"] = aoe_attack_key or main_attack_key
    else:
        if main_attack_key:
            cfg["key"]["directional_attack"] = main_attack_key
        if aoe_attack_key:
            cfg["key"]["aoe_skill"] = aoe_attack_key

    for function_id, cfg_key in LEGACY_ACTION_KEY_MAP.items():
        if bindings.get(function_id):
            cfg["key"][cfg_key] = bindings[function_id]

    legacy_buff = bindings.get("buff", "") or bindings.get("buff_pet_food", "")
    buff_slots = collect_buff_skill_slots(bindings, intervals)
    if not buff_slots and legacy_buff:
        buff_slots = [(
            "buff",
            legacy_buff,
            int(intervals.get("buff", intervals.get("buff_pet_food", 60))),
        )]
    if buff_slots:
        cfg["buff_skill"]["keys"] = [key for _, key, _ in buff_slots]
        cfg["buff_skill"]["cooldown"] = [cooldown for _, _, cooldown in buff_slots]

    # Profession-specific engine tuning via profile overrides.
    # Profiles with empty `overrides` leave general config untouched.
    if has_profile and overrides:
        for section, values in overrides.items():
            if section not in OVERRIDE_SECTIONS:
                continue
            if not isinstance(values, dict):
                continue
            if section not in cfg or not isinstance(cfg.get(section), dict):
                cfg[section] = {}
            _deep_update(cfg[section], values)


def resolve_profession_binding(cfg, action_id):
    """Resolve a semantic action id to the selected profession's game key."""
    profession = cfg.get(RUNTIME_CONFIG_KEY, {})
    if not isinstance(profession, dict):
        profession = {}
    bindings = profession.get("bindings", {})
    if not isinstance(bindings, dict):
        bindings = {}

    key = bindings.get(action_id, "")
    if key:
        return key

    # A range-based main attack remains a valid AoE action when the user has
    # not configured a separate AoE key.
    if (
        action_id == "aoe_attack"
        and profession.get("main_attack_type") == "aoe_skill"
    ):
        return bindings.get("main_attack", "") or cfg.get("key", {}).get("aoe_skill", "")

    legacy_keys = cfg.get("key", {})
    if action_id == "main_attack":
        attack_type = cfg.get("bot", {}).get("attack", "directional")
        key_name = "aoe_skill" if attack_type == "aoe_skill" else "directional_attack"
        return legacy_keys.get(key_name, "")
    if action_id == "aoe_attack":
        return legacy_keys.get("aoe_skill", "")
    if action_id in LEGACY_ACTION_KEY_MAP:
        return legacy_keys.get(LEGACY_ACTION_KEY_MAP[action_id], "")
    if action_id in ("buff", "buff_pet_food"):
        buff_keys = cfg.get("buff_skill", {}).get("keys", [])
        return buff_keys[0] if buff_keys else ""
    return ""
