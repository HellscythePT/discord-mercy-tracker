from config import VALID_SHARD_TYPES
from utils import format_progress_bar

def update_tracker(data, shard_type, amount):
    """Update the mercy tracker data for a specific shard type"""
    if shard_type not in data:
        data[shard_type] = 0
    data[shard_type] += amount

def validate_shard_type(shard_type):
    """Validate if the shard type is supported"""
    return shard_type.lower() in VALID_SHARD_TYPES

def get_mercy_rules():
    """Get the mercy rules dictionary"""
    return {
        "ancient": {
            "legendary": {"start": 200, "rate": 5}
        },
        "void": {
            "legendary": {"start": 200, "rate": 5}
        },
        "sacred": {
            "legendary": {"start": 12, "rate": 2}
        },
        "primal": {
            "legendary": {"start": 75, "rate": 1},
            "mythical": {"start": 200, "rate": 10}
        },
        "remnant": {
            "mythical": {"start": 24, "rate": 1}
        }
    }

def get_status(data):
    """Generate a formatted status report for the user's mercy progress"""
    mercy_rules = get_mercy_rules()
    lines = []

    # Handle Primal output specially
    primal_legendary = data.get("primal_legendary", 0)
    primal_mythical = data.get("primal_mythical", 0)
    if primal_legendary > 0 or primal_mythical > 0:
        total_primal = max(primal_legendary, primal_mythical)
        lines.append(f"\n**Primal Shards** ({total_primal} total)")
        # Legendary
        rule = mercy_rules["primal"]["legendary"]
        start_mercy = rule["start"]
        rate_increase = rule["rate"]
        progress = primal_legendary / start_mercy if start_mercy else 0
        progress_bar = format_progress_bar(progress, 10)
        percent = int(progress * 100)
        if primal_legendary < start_mercy:
            remaining = start_mercy - primal_legendary
            lines.append(f"└ Legendary: {remaining} to mercy {progress_bar} {percent}% ({primal_legendary}/{start_mercy})")
        else:
            extra = primal_legendary - start_mercy
            chance_increase = extra * rate_increase
            lines.append(f"└ Legendary: **MERCY ACTIVE** (+{chance_increase}% chance)")
        # Mythical
        rule = mercy_rules["primal"]["mythical"]
        start_mercy = rule["start"]
        rate_increase = rule["rate"]
        progress = primal_mythical / start_mercy if start_mercy else 0
        progress_bar = format_progress_bar(progress, 10)
        percent = int(progress * 100)
        if primal_mythical < start_mercy:
            remaining = start_mercy - primal_mythical
            lines.append(f"└ Mythical: {remaining} to mercy {progress_bar} {percent}% ({primal_mythical}/{start_mercy})")
        else:
            extra = primal_mythical - start_mercy
            chance_increase = extra * rate_increase
            lines.append(f"└ Mythical: **MERCY ACTIVE** (+{chance_increase}% chance)")

    # Show all other shards
    for shard_type, count in data.items():
        if shard_type in ("primal_legendary", "primal_mythical"):
            continue
        if shard_type not in mercy_rules:
            continue
        lines.append(f"\n**{shard_type.title()} Shards** ({count} total)")
        for rarity, rule in mercy_rules[shard_type].items():
            start_mercy = rule["start"]
            rate_increase = rule["rate"]
            progress = count / start_mercy if start_mercy else 0
            progress_bar = format_progress_bar(progress, 10)
            percent = int(progress * 100)
            if count < start_mercy:
                remaining = start_mercy - count
                lines.append(f"└ {rarity.title()}: {remaining} to mercy {progress_bar} {percent}% ({count}/{start_mercy})")
            else:
                extra = count - start_mercy
                chance_increase = extra * rate_increase
                lines.append(f"└ {rarity.title()}: **MERCY ACTIVE** (+{chance_increase}% chance)")

    if not lines:
        return "No mercy data tracked yet. Use `/open` to start tracking!"

    return "\n".join(lines)

def get_mercy_rules_info():
    """Get formatted mercy rules information"""
    mercy_rules = get_mercy_rules()
    info_lines = []
    
    for shard_type, rules in mercy_rules.items():
        info_lines.append(f"\n**{shard_type.title()} Shards:**")
        for rarity, rule in rules.items():
            start = rule["start"]
            rate = rule["rate"]
            info_lines.append(f"└ {rarity.title()}: Mercy at {start} summons (+{rate}% per summon after)")
    
    return "\n".join(info_lines)

def calculate_mercy_chance(current_count, mercy_start, rate_per_summon):
    """Calculate the current mercy chance percentage"""
    if current_count < mercy_start:
        return 0
    
    extra_summons = current_count - mercy_start
    return extra_summons * rate_per_summon

def get_detailed_status(data):
    """Get detailed status with percentages and progress"""
    mercy_rules = get_mercy_rules()
    detailed_info = {}

    # Handle Primal Legendary
    primal_legendary = data.get("primal_legendary", 0)
    if primal_legendary > 0:
        rule = mercy_rules["primal"]["legendary"]
        start_mercy = rule["start"]
        rate_increase = rule["rate"]
        if primal_legendary < start_mercy:
            remaining = start_mercy - primal_legendary
            progress_percent = (primal_legendary / start_mercy) * 100
            chance_increase = 0
            active = False
        else:
            remaining = 0
            progress_percent = 100
            chance_increase = (primal_legendary - start_mercy) * rate_increase
            active = True
        detailed_info["primal_legendary"] = {
            "count": primal_legendary,
            "mercy_status": {
                "legendary": {
                    "active": active,
                    "remaining": remaining,
                    "progress_percent": progress_percent,
                    "chance_increase": chance_increase
                }
            }
        }

    # Handle Primal Mythical
    primal_mythical = data.get("primal_mythical", 0)
    if primal_mythical > 0:
        rule = mercy_rules["primal"]["mythical"]
        start_mercy = rule["start"]
        rate_increase = rule["rate"]
        if primal_mythical < start_mercy:
            remaining = start_mercy - primal_mythical
            progress_percent = (primal_mythical / start_mercy) * 100
            chance_increase = 0
            active = False
        else:
            remaining = 0
            progress_percent = 100
            chance_increase = (primal_mythical - start_mercy) * rate_increase
            active = True
        detailed_info["primal_mythical"] = {
            "count": primal_mythical,
            "mercy_status": {
                "mythical": {
                    "active": active,
                    "remaining": remaining,
                    "progress_percent": progress_percent,
                    "chance_increase": chance_increase
                }
            }
        }

    # Handle all other shards
    for shard_type, count in data.items():
        if shard_type in ("primal_legendary", "primal_mythical"):
            continue
        if shard_type not in mercy_rules:
            continue

        detailed_info[shard_type] = {
            "count": count,
            "mercy_status": {}
        }

        for rarity, rule in mercy_rules[shard_type].items():
            start_mercy = rule["start"]
            rate_increase = rule["rate"]

            if count < start_mercy:
                remaining = start_mercy - count
                progress_percent = (count / start_mercy) * 100
                chance_increase = 0
                active = False
            else:
                remaining = 0
                progress_percent = 100
                chance_increase = (count - start_mercy) * rate_increase
                active = True

            detailed_info[shard_type]["mercy_status"][rarity] = {
                "active": active,
                "remaining": remaining,
                "progress_percent": progress_percent,
                "chance_increase": chance_increase
            }

    return detailed_info