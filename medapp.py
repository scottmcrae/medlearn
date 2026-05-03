import chainlit as cl
import anthropic
import os

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-20250514"

SPECIALTIES = [
    "Internal medicine", "Emergency medicine", "Family medicine",
    "Cardiology", "Pulmonology", "Neurology", "Nephrology",
    "Gastroenterology", "Infectious disease", "Hematology/Oncology",
    "Endocrinology", "Rheumatology", "OB/GYN", "Pediatrics", "Psychiatry"
]

FORMATS = {
    "short": "short vignette (2-3 sentences, chief complaint only)",
    "full": "full vignette (HPI, ROS, PMH, meds, allergies, exam findings, labs)",
    "hospital": "hospital course note (admission through disposition)",
    "soap": "SOAP note",
    "ed": "ED triage scenario (triage vitals, chief complaint, brief history)",
}

COMPLEXITIES = [
    "Straightforward / classic presentation",
    "Moderate / some atypical features",
    "Complex / multiple comorbidities",
    "Red herring / trick case",
]


def build_generate_prompt(specialty, fmt_key, complexity, custom_topic):
    fmt_label = FORMATS[fmt_key]
    topic_clause = f"The case should involve: {custom_topic}." if custom_topic else ""
    return f"""Generate a realistic medical case as a {fmt_label} in {specialty}.
Complexity: {complexity}.
{topic_clause}

Requirements:
- Realistic patient demographics, vitals, and clinical details
- For full vignettes: include CC, HPI, relevant PMH/meds, pertinent positives and negatives on exam
- For hospital courses: admission reason, key hospital day events, decision points, disposition
- For SOAP: standard SOAP structure
- For ED triage: triage vitals, CC, brief history
- Do NOT reveal the diagnosis or management answer — leave it open for discussion
- End with a clear clinical question or decision point

Output only the case text, no preamble or labels."""


def build_system_prompt(case_text, mode):
    mode_instruction = (
        "Answer the learner's questions directly and educationally. Be concise but thorough."
        if mode == "answer"
        else
        "You are Socratic. Do NOT give answers directly. Instead, ask the learner guiding questions "
        "that help them reason toward the answer themselves. Only confirm or correct after they've committed to an answer."
    )
    return f"""You are an experienced attending physician and clinical educator discussing a medical case with a learner.

TUTOR MODE: {mode_instruction}

Your goals:
- Foster clinical reasoning, not memorization
- Address differential diagnosis, workup, pathophysiology, and management
- Do not reveal the diagnosis unless the learner has reasoned to it or explicitly asks
- Keep teaching points grounded in this specific case

THE CASE:
{case_text}"""


@cl.on_chat_start
async def start():
    cl.user_session.set("case", None)
    cl.user_session.set("history", [])
    cl.user_session.set("mode", "answer")

    await show_menu()


async def show_menu():
    await cl.Message(
        content=(
            "## Medical Case Tutor\n\n"
            "Configure your case below, then type **generate** to start.\n\n"
            "**Specialty** (type the number):\n"
            + "\n".join(f"{i+1}. {s}" for i, s in enumerate(SPECIALTIES))
            + "\n\n**Format** (type the key):\n"
            + "\n".join(f"- `{k}` — {v}" for k, v in FORMATS.items())
            + "\n\n**Complexity** (type the number):\n"
            + "\n".join(f"{i+1}. {c}" for i, c in enumerate(COMPLEXITIES))
            + "\n\n**Tutor mode:** type `socratic` or `answer` to switch at any time.\n\n"
            "---\n"
            "**Defaults:** Internal medicine · full vignette · Moderate\n\n"
            "Type `generate` to use defaults, or set options first:\n"
            "```\nspecialty 3\nformat ed\ncomplexity 4\ntopic chest pain and syncope\ngenerate\n```"
        )
    ).send()

    cl.user_session.set("specialty", SPECIALTIES[0])
    cl.user_session.set("format", "full")
    cl.user_session.set("complexity", COMPLEXITIES[1])
    cl.user_session.set("topic", "")


@cl.on_message
async def on_message(message: cl.Message):
    text = message.content.strip()
    lower = text.lower()

    # --- Mode switch ---
    if lower in ("socratic", "answer"):
        cl.user_session.set("mode", lower)
        mode_label = "Socratic" if lower == "socratic" else "Answer on demand"
        await cl.Message(content=f"Tutor mode switched to **{mode_label}**.").send()
        return

    # --- Config commands ---
    if lower.startswith("specialty "):
        val = text[10:].strip()
        if val.isdigit() and 1 <= int(val) <= len(SPECIALTIES):
            cl.user_session.set("specialty", SPECIALTIES[int(val) - 1])
            await cl.Message(content=f"Specialty set to **{SPECIALTIES[int(val)-1]}**.").send()
        else:
            await cl.Message(content="Invalid specialty number.").send()
        return

    if lower.startswith("format "):
        val = text[7:].strip().lower()
        if val in FORMATS:
            cl.user_session.set("format", val)
            await cl.Message(content=f"Format set to **{val}**.").send()
        else:
            await cl.Message(content=f"Valid formats: {', '.join(FORMATS.keys())}").send()
        return

    if lower.startswith("complexity "):
        val = text[11:].strip()
        if val.isdigit() and 1 <= int(val) <= len(COMPLEXITIES):
            cl.user_session.set("complexity", COMPLEXITIES[int(val) - 1])
            await cl.Message(content=f"Complexity set to **{COMPLEXITIES[int(val)-1]}**.").send()
        else:
            await cl.Message(content="Invalid complexity number.").send()
        return

    if lower.startswith("topic "):
        val = text[6:].strip()
        cl.user_session.set("topic", val)
        await cl.Message(content=f"Topic set to: **{val}**").send()
        return

    if lower == "new" or lower == "reset":
        cl.user_session.set("case", None)
        cl.user_session.set("history", [])
        await cl.Message(content="Case cleared. Type `generate` for a new one.").send()
        return

    if lower == "menu" or lower == "help":
        await show_menu()
        return

    # --- Generate case ---
    if lower == "generate":
        specialty = cl.user_session.get("specialty")
        fmt = cl.user_session.get("format")
        complexity = cl.user_session.get("complexity")
        topic = cl.user_session.get("topic")

        prompt = build_generate_prompt(specialty, fmt, complexity, topic)

        msg = cl.Message(content="")
        await msg.send()

        case_text = ""
        with client.messages.stream(
            model=MODEL,
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            for delta in stream.text_stream:
                case_text += delta
                await msg.stream_token(delta)

        await msg.update()

        cl.user_session.set("case", case_text)
        cl.user_session.set("history", [])

        mode = cl.user_session.get("mode")
        mode_label = "Socratic" if mode == "socratic" else "Answer on demand"
        await cl.Message(
            content=(
                f"---\n*{specialty} · {fmt} · {complexity}*\n\n"
                f"Tutor mode: **{mode_label}** (type `socratic` or `answer` to switch)\n\n"
                "Ask anything about this case, or type `new` to generate another."
            )
        ).send()
        return

    # --- Tutor chat ---
    case_text = cl.user_session.get("case")
    if not case_text:
        await cl.Message(
            content="No case loaded. Type `generate` to create one."
        ).send()
        return

    history = cl.user_session.get("history")
    mode = cl.user_session.get("mode")
    system = build_system_prompt(case_text, mode)

    history.append({"role": "user", "content": text})

    msg = cl.Message(content="")
    await msg.send()

    reply = ""
    with client.messages.stream(
        model=MODEL,
        max_tokens=1000,
        system=system,
        messages=history
    ) as stream:
        for delta in stream.text_stream:
            reply += delta
            await msg.stream_token(delta)

    await msg.update()
    history.append({"role": "assistant", "content": reply})
    cl.user_session.set("history", history)
