RECIPES = {
    "summary": (
        "Summarize the notes into **concise, complete bullets** with sections:\n"
        "Decisions, Actions (with owners), Risks. Keep important numbers.\n"
        "Format:\n"
        "Decisions:\n- …\nActions:\n- Owner: … — …\nRisks:\n- …\n\nInput:\n"
    ),
    "action_items": (
        "Extract **actionable tasks** with owners and deadlines if present.\n"
        "Return bullets in the format:\n"
        "- Owner: <name> — <verb-first task> (due <date> if any)\n\nInput:\n"
    ),
    "brainstorm": (
        "Brainstorm 8–12 **practical, non-obvious** ideas. Use short bullets.\n\nInput:\n"
    ),
}
