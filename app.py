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


def get_status():
    specialty = cl.user_session.get("specialty", SPECIALTIES[0])
    fmt = cl.user_session.get("format", "full")
    complexity = cl.user_session.get("complexity", COMPLEXITIES[1])
    mode = cl.user_session.get("mode", "answer")
    topic = cl.user_session.get("topic", "")
    topic_str = f" · topic: {topic}" if topic else ""
    mode_label = "Socratic" if mode == "socratic" else "Answer"
    return f"**{specialty}** · {fmt} · {complexity.split('/')[0].strip()}{topic_str} · tutor: {mode_label}"


async def show_controls():
    # Specialty buttons
    await cl.Message(content="**Specialty:**").send()
    specialty_actions = [
        cl.Action(name="set_specialty", value=s, label=s)
        for s in SPECIALTIES
    ]
    await cl.Message(content="", actions=specialty_actions).send()

    # Format buttons
    await cl.Message(content="**Format:**").send()
    format_actions = [
        cl.Action(name="set_format", value=k, label=k.upper())
        for k in FORMATS.keys()
    ]
    await cl.Message(content="", actions=format_actions).send()

    # Complexity buttons
    await cl.Message(content="**Complexity:**").send()
    complexity_actions = [
        cl.Action(name="set_complexity", value=c, label=c.split("/")[0].strip())
        for c in COMPLEXITIES
    ]
    await cl.Message(content="", actions=complexity_actions).send()

    # Tutor mode buttons
    await cl.Message(content="**Tutor mode:**").send()
    mode_actions = [
        cl.Action(name="set_mode", value="answer", label="Answer mode"),
        cl.Action(name="set_mode", value="socratic", label="Socratic mode"),
    ]
    await cl.Message(content="", actions=mode_actions).send()

    # Generate / New buttons
    main_actions = [
        cl.Action(name="generate", value="generate", label="⚡ Generate case"),
        cl.Action(name="new_case", value="new", label="🔄 New case"),
    ]
    await cl.Message(content=get_status(), actions=main_actions).send()


@cl.action_callback("set_specialty")
async def set_specialty(action: cl.Action):
    cl.user_session.set("specialty", action.value)
    await cl.Message(content=f"Specialty → **{action.value}**").send()


@cl.action_callback("set_format")
async def set_format(action: cl.Action):
    cl.user_session.set("format", action.value)
    await cl.Message(content=f"Format → **{action.value}** ({FORMATS[action.value]})").send()


@cl.action_callback("set_complexity")
async def set_complexity(action: cl.Action):
    cl.user_session.set("complexity", action.value)
    await cl.Message(content=f"Complexity → **{action.value}**").send()


@cl.action_callback("set_mode")
async def set_mode(action: cl.Action):
    cl.user_session.set("mode", action.value)
    label = "Socratic" if action.value == "socratic" else "Answer on demand"
    await cl.Message(content=f"Tutor mode → **{label}**").send()


@cl.action_callback("generate")
async def on_generate(action: cl.Action):
    await do_generate()


@cl.action_callback("new_case")
async def on_new_case(action: cl.Action):
    cl.user_session.set("case", None)
    cl.user_session.set("history", [])
    await cl.Message(content="Case cleared.").send()
    await show_controls()


async def do_generate():
    specialty = cl.user_session.get("specialty", SPECIALTIES[0])
    fmt = cl.user_session.get("format", "full")
    complexity = cl.user_session.get("complexity", COMPLEXITIES[1])
    topic = cl.user_session.get("topic", "")

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

    mode = cl.user_session.get("mode", "answer")
    mode_label = "Socratic" if mode == "socratic" else "Answer on demand"

    quick_actions = [
        cl.Action(name="quick_ask", value="What is your differential diagnosis?", label="DDx"),
        cl.Action(name="quick_ask", value="What is the most important next step?", label="Next step"),
        cl.Action(name="quick_ask", value="What labs and imaging would you order and why?", label="Labs & imaging"),
        cl.Action(name="quick_ask", value="Walk me through the management plan.", label="Management"),
        cl.Action(name="quick_ask", value="What are the can't-miss diagnoses here?", label="Can't miss"),
        cl.Action(name="quick_ask", value="What teaching points does this case illustrate?", label="Teaching points"),
        cl.Action(name="new_case", value="new", label="🔄 New case"),
    ]
    await cl.Message(
        content=f"*{specialty} · {fmt} · tutor: {mode_label}*\n\nAsk anything, or use a quick prompt:",
        actions=quick_actions
    ).send()


@cl.action_callback("quick_ask")
async def quick_ask(action: cl.Action):
    await do_chat(action.value)


async def do_chat(text: str):
    case_text = cl.user_session.get("case")
    if not case_text:
        await cl.Message(content="No case loaded. Hit **Generate case** first.").send()
        return

    history = cl.user_session.get("history", [])
    mode = cl.user_session.get("mode", "answer")
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


@cl.on_chat_start
async def start():
    cl.user_session.set("case", None)
    cl.user_session.set("history", [])
    cl.user_session.set("mode", "answer")
    cl.user_session.set("specialty", SPECIALTIES[0])
    cl.user_session.set("format", "full")
    cl.user_session.set("complexity", COMPLEXITIES[1])
    cl.user_session.set("topic", "")
    await cl.Message(content="## Medical Case Tutor\nConfigure your case below and hit **Generate**.").send()
    await show_controls()


@cl.on_message
async def on_message(message: cl.Message):
    # Init guard
    if cl.user_session.get("specialty") is None:
        cl.user_session.set("case", None)
        cl.user_session.set("history", [])
        cl.user_session.set("mode", "answer")
        cl.user_session.set("specialty", SPECIALTIES[0])
        cl.user_session.set("format", "full")
        cl.user_session.set("complexity", COMPLEXITIES[1])
        cl.user_session.set("topic", "")
        await cl.Message(content="## Medical Case Tutor").send()
        await show_controls()
        return

    text = message.content.strip()
    lower = text.lower()

    if lower in ("menu", "help", "reset", "new"):
        cl.user_session.set("case", None)
        cl.user_session.set("history", [])
        await show_controls()
        return

    if lower == "generate":
        await do_generate()
        return

    if lower.startswith("topic "):
        val = text[6:].strip()
        cl.user_session.set("topic", val)
        await cl.Message(content=f"Topic → **{val}**").send()
        return

    # Otherwise treat as tutor chat
    await do_chat(text)
