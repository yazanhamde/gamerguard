# قائمة الألعاب الجاهزة — الأدمن يختار منها في الداش
GAMES = [
    # ── FPS / Battle Royale ──────────────────────────────────────────
    {
        "id": "valorant", "name": "Valorant", "category": "FPS / Battle Royale", "emoji": "🎯",
        "ranks": ["Iron", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Ascendant", "Immortal", "Radiant"],
    },
    {
        "id": "fortnite", "name": "Fortnite", "category": "FPS / Battle Royale", "emoji": "🏗️",
        "ranks": ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Elite", "Champion", "Unreal"],
    },
    {
        "id": "apex", "name": "Apex Legends", "category": "FPS / Battle Royale", "emoji": "🔫",
        "ranks": ["Rookie", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master", "Predator"],
    },
    {
        "id": "warzone", "name": "Call of Duty: Warzone", "category": "FPS / Battle Royale", "emoji": "💥",
        "ranks": ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Crimson", "Iridescent", "Top 250"],
    },
    {
        "id": "cs2", "name": "Counter-Strike 2", "category": "FPS / Battle Royale", "emoji": "🖥️",
        "ranks": ["Silver I", "Silver II", "Silver III", "Silver IV", "Silver Elite", "Silver Elite Master",
                  "Gold Nova I", "Gold Nova II", "Gold Nova III", "Gold Nova Master",
                  "Master Guardian I", "Master Guardian II", "Master Guardian Elite", "Distinguished Master Guardian",
                  "Legendary Eagle", "Legendary Eagle Master", "Supreme", "Global Elite"],
    },

    # ── بقاء وتعاون (ما في رانك رسمي) ──────────────────────────────
    {
        "id": "minecraft", "name": "Minecraft", "category": "بقاء وتعاون", "emoji": "⛏️",
        "ranks": [],   # بدون رانك
    },
    {
        "id": "lethal", "name": "Lethal Company", "category": "بقاء وتعاون", "emoji": "👻",
        "ranks": [],
    },
    {
        "id": "rust", "name": "Rust", "category": "بقاء وتعاون", "emoji": "🪓",
        "ranks": [],
    },
    {
        "id": "palworld", "name": "Palworld", "category": "بقاء وتعاون", "emoji": "🐾",
        "ranks": [],
    },
    {
        "id": "among_us", "name": "Among Us", "category": "بقاء وتعاون", "emoji": "🕵️",
        "ranks": [],
    },

    # ── MOBA / RPG ───────────────────────────────────────────────────
    {
        "id": "lol", "name": "League of Legends", "category": "MOBA / RPG", "emoji": "⚔️",
        "ranks": ["Iron", "Bronze", "Silver", "Gold", "Platinum", "Emerald", "Diamond", "Master", "Grandmaster", "Challenger"],
    },
    {
        "id": "genshin", "name": "Genshin Impact", "category": "MOBA / RPG", "emoji": "🌸",
        "ranks": ["AR 1-20", "AR 21-35", "AR 36-45", "AR 46-55", "AR 56-60"],  # Adventure Rank
    },
    {
        "id": "roblox", "name": "Roblox", "category": "MOBA / RPG", "emoji": "🧱",
        "ranks": [],
    },
    {
        "id": "dota2", "name": "Dota 2", "category": "MOBA / RPG", "emoji": "🏆",
        "ranks": ["Herald", "Guardian", "Crusader", "Archon", "Legend", "Ancient", "Divine", "Immortal"],
    },

    # ── رياضة وسباقات ────────────────────────────────────────────────
    {
        "id": "fc25", "name": "EA FC 25", "category": "رياضة وسباقات", "emoji": "⚽",
        "ranks": ["Division 10", "Division 9", "Division 8", "Division 7", "Division 6",
                  "Division 5", "Division 4", "Division 3", "Division 2", "Division 1", "Elite"],
    },
    {
        "id": "rocket", "name": "Rocket League", "category": "رياضة وسباقات", "emoji": "🚗",
        "ranks": ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Champion", "Grand Champion", "Supersonic Legend"],
    },
]

GAMES_BY_ID = {g["id"]: g for g in GAMES}
CATEGORIES  = list(dict.fromkeys(g["category"] for g in GAMES))