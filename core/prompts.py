from dataclasses import dataclass
from typing import Callable, Dict

@dataclass
class Recipe:
    name: str
    build_prompt: Callable[[str], str]

def _summary_prompt(text: str) -> str:
    # t5-small is best at summarization with the "summarize:" prefix
    return f"summarize: {text}"

def _action_items_prompt(text: str) -> str:
    # Not native to t5-small, but works for a demo
    return (
        "extract concise action items with owners and deadlines if present. "
        "respond as bullet points.\n\n"
        f"{text}"
    )

def _brainstorm_prompt(text: str) -> str:
    return (
        "brainstorm 5 short ideas to move this forward. use numbered list.\n\n"
        f"{text}"
    )

RECIPES: Dict[str, Recipe] = {
    "summary":      Recipe("summary", _summary_prompt),
    "action_items": Recipe("action_items", _action_items_prompt),
    "brainstorm":   Recipe("brainstorm", _brainstorm_prompt),
}

def list_recipes() -> Dict[str, str]:
    return {k: v.name for k, v in RECIPES.items()}

def apply_recipe(recipe_name: str, text: str) -> str:
    recipe = RECIPES.get(recipe_name)
    if not recipe:
        raise ValueError(f"Unknown recipe '{recipe_name}'. Available: {', '.join(RECIPES.keys())}")
    return recipe.build_prompt(text)
