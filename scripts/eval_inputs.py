"""Run the reference inputs through every signal and the scorer, printing each score separately.

Usage:  .venv/bin/python scripts/eval_inputs.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scoring import combine  # noqa: E402
from signals import run_all, words  # noqa: E402

INPUTS = {
    "clear_ai": (
        "Artificial intelligence represents a transformative paradigm shift in modern society. "
        "It is important to note that while the benefits of AI are numerous, it is equally "
        "essential to consider the ethical implications. Furthermore, stakeholders across "
        "various sectors must collaborate to ensure responsible deployment."
    ),
    "clear_human": (
        "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the "
        "broth was fine but they put WAY too much sodium in it and i was thirsty for like three "
        "hours after. my friend got the spicy version and said it was better. probably won't go "
        "back unless someone drags me there"
    ),
    "borderline_formal_human": (
        "The relationship between monetary policy and asset price inflation has been extensively "
        "studied in the literature. Central banks face a fundamental tension between their "
        "mandate for price stability and the unintended consequences of prolonged low interest "
        "rates on equity and real estate valuations."
    ),
    "borderline_edited_ai": (
        "I've been thinking a lot about remote work lately. There are genuine tradeoffs — "
        "flexibility and no commute on one side, isolation and blurred work-life boundaries on "
        "the other. Studies show productivity varies widely by individual and role type."
    ),
    "short_repetitive_poem": (
        "I wait by the door.\nI wait by the door.\nThe kettle sings, the light goes thin,\n"
        "and still I wait by the door."
    ),
}


def main() -> None:
    header = f"{'input':<26}{'llm':>6}{'stylo':>7}{'mark':>6}{'ai_lik':>8}{'conf':>6}  attribution"
    print(header)
    print("-" * len(header))
    for name, text in INPUTS.items():
        sig = run_all(text)
        res = combine(sig, len(words(text)))
        llm = sig["llm"]["score"]
        print(
            f"{name:<26}{'n/a' if llm is None else f'{llm:.2f}':>6}"
            f"{sig['stylometric']['score']:>7.2f}{sig['markers']['score']:>6.2f}"
            f"{res['ai_likelihood']:>8.3f}{res['confidence']:>6.2f}  {res['attribution']}"
            + ("  (signals disagree)" if res["scoring_notes"]["signals_disagree"] else "")
        )
        if llm is None:
            print("    llm error:", sig["llm"]["details"].get("error"))


if __name__ == "__main__":
    main()
