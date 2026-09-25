#!/usr/bin/env python3

from pathlib import Path
import argparse
import html
import json
import re
import sys


ROOT = Path(__file__).resolve().parents[1]

SRC = ROOT / "imports/ap_statistics_exams/txt"
PDF_SRC = ROOT / "imports/ap_statistics_exams/pdf"
PROBLEMS = ROOT / "imports/ap_statistics_exams/problem_files"

OUT = ROOT / "packs/ap-statistics/data"
PDF_OUT = ROOT / "packs/ap-statistics/pdf"
CONFIG = ROOT / "packs/ap-statistics/config.json"


TXT_RE = re.compile(
    r"^ap_statistics_(mcq|frq)_exam_(\d{2})\.txt$",
    re.I,
)

PDF_RE = re.compile(
    r"^ap_statistics_(mcq|frq)_exam_(\d{2})\.pdf$",
    re.I,
)

ID_RE = re.compile(
    r"^(APSTAT-(MCQ|FRQ)(\d+)-(\d{3}))$",
    re.I,
)

CHOICE_RE = re.compile(
    r"^([A-D])[\)\.]\s*(.*)$"
)

KEY_RE = re.compile(
    r"^(APSTAT-MCQ(\d+)-\d{3})\s*(?:[—–-]|,)\s*"
    r"Correct:\s*([A-D])\s*(?:[—–-]|,)\s*"
    r"Correct Answer:\s*(.*?)\s*(?:[—–-]|,)\s*"
    r"Explanation:\s*(.+)$",
    re.I,
)


UNITS = {
    1: "Exploring One-Variable Data and Collecting Data",
    2: "Probability, Random Variables, and Probability Distributions",
    3: "Inference for Categorical Data: Proportions",
    4: "Inference for Quantitative Data: Means",
    5: "Regression Analysis",
}


FIELDS = {
    "section": "section",
    "type": "type",
    "unit": "unit",
    "primary unit": "primaryUnit",
    "secondary unit": "secondaryUnit",
    "skill": "skill",

    "statistical practices": "statisticalPracticesRaw",
    "statistical practice": "statisticalPracticesRaw",
    "practices": "statisticalPracticesRaw",

    "primary practices": "primaryPracticesRaw",
    "primary statistical practices": "primaryPracticesRaw",

    "stimulus id": "stimulusId",
    "set id": "stimulusId",

    "stimulus": "stimulus",
    "scenario": "stimulus",
    "context": "stimulus",

    "dataset": "dataset",
    "data set": "dataset",
    "table": "table",

    "prompt": "prompt",
    "question": "prompt",

    "parts": "subparts",
    "subparts": "subparts",

    "frq type": "frqType",
    "question type": "frqType",

    "point breakdown": "pointAllocation",

    "correct": "correct",
    "answer": "correct",
    "correct answer": "correctAnswerText",
    "explanation": "explanation",

    "expected points": "expectedPoints",
    "points": "expectedPoints",

    "point allocation": "pointAllocation",
    "scoring guide": "scoringGuide",

    "model response": "modelResponse",
    "model guidance": "modelGuidance",
    "model answer": "modelResponse",
}


MULTI = {
    "stimulus",
    "dataset",
    "table",
    "prompt",
    "subparts",
    "explanation",
    "pointAllocation",
    "scoringGuide",
    "modelResponse",
    "modelGuidance",
}


KEY_HEADINGS = [
    "PART B — ANSWER KEY + EXPLANATIONS",
    "PART B – ANSWER KEY + EXPLANATIONS",
    "PART B - ANSWER KEY + EXPLANATIONS",
    "ANSWER KEY + EXPLANATIONS",
    "ANSWER KEY AND EXPLANATIONS",
    "ANSWER KEY",
]


def ns(value):
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def nm(value):
    lines = (
        str(value or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .split("\n")
    )

    while lines and not lines[0].strip():
        lines.pop(0)

    while lines and not lines[-1].strip():
        lines.pop()

    return "\n".join(
        line.rstrip()
        for line in lines
    ).strip()



def strip_trailing_nonimport(text):
    lines = text.splitlines()

    for index, line in enumerate(lines):
        normalized = " ".join(line.upper().split())

        markers = (
            "DO NOT IMPORT",
            "DO-NOT-IMPORT",
            "DO_NOT_IMPORT",
            "DO-NOT-REPEAT BANK UPDATE",
            "DO NOT REPEAT BANK UPDATE",
        )

        if any(marker in normalized for marker in markers):
            return "\n".join(lines[:index]).rstrip() + "\n"

    return text


def file_info(path):
    match = TXT_RE.fullmatch(path.name)

    if not match:
        raise ValueError(
            f"{path.name}: invalid filename; expected "
            "ap_statistics_mcq_exam_XX.txt or "
            "ap_statistics_frq_exam_XX.txt"
        )

    return (
        match.group(1).lower(),
        int(match.group(2)),
    )


def split_key(text):
    upper = text.upper()

    hits = [
        (
            upper.find(heading.upper()),
            heading,
        )
        for heading in KEY_HEADINGS
        if upper.find(heading.upper()) >= 0
    ]

    if not hits:
        return text, ""

    pos, heading = min(hits)

    return (
        text[:pos],
        text[pos + len(heading):],
    )


def parse_key(text):
    output = {}
    bad = []

    for raw in text.splitlines():
        line = raw.strip()

        if not line:
            continue

        if not line.upper().startswith("APSTAT-MCQ"):
            continue

        match = KEY_RE.fullmatch(line)

        if not match:
            bad.append(line)
            continue

        qid, exam_no, letter, answer, explanation = match.groups()

        qid = qid.upper()

        if qid in output:
            bad.append(
                "DUPLICATE KEY: " + line
            )
            continue

        output[qid] = {
            "exam": int(exam_no),
            "correct": letter.upper(),
            "answer": ns(answer),
            "explanation": ns(explanation),
        }

    return output, bad


def base_item(
    qid,
    kind,
    exam,
    number,
):
    return {
        "id": qid.upper(),

        "section": kind.upper(),
        "type": kind.lower(),
        "itemType": kind.lower(),

        "examNumber": exam,
        "questionNumber": number,

        "unit": "",
        "primaryUnit": "",
        "secondaryUnit": "",
        "skill": "",

        "statisticalPracticesRaw": "",
        "primaryPracticesRaw": "",

        "statisticalPractices": [],
        "primaryPractices": [],

        "stimulusId": "",
        "stimulus": "",
        "dataset": "",
        "table": "",

        "prompt": "",
        "subparts": "",

        "choices": {},

        "correct": "",
        "correctAnswerText": "",
        "explanation": "",

        "frqType": "",
        "expectedPoints": "",

        "pointAllocation": "",
        "scoringGuide": "",

        "modelResponse": "",
        "modelGuidance": "",
    }


def add(item, field, value):
    value = value.rstrip()

    if not value:
        return

    if item.get(field):
        item[field] += "\n" + value
    else:
        item[field] = value


def parse_block(
    qid,
    kind,
    exam,
    number,
    lines,
):
    item = base_item(
        qid,
        kind,
        exam,
        number,
    )

    field = None
    choice = None

    for raw in lines:
        stripped = raw.strip()

        if (
            kind == "FRQ"
            and re.match(
                r"^[·•-]\s*APSTAT-FRQ\d+-\d{3}\s*:",
                stripped,
                re.I,
            )
        ):
            break

        if not stripped:
            if (
                field in MULTI
                and item.get(field)
            ):
                item[field] += "\n"

            elif (
                choice
                and item["choices"].get(choice)
            ):
                item["choices"][choice] += "\n"

            continue

        if ":" in stripped:
            label, value = stripped.split(
                ":",
                1,
            )

            mapped = FIELDS.get(
                ns(label).lower()
            )

            if mapped:
                field = mapped
                choice = None

                if mapped in MULTI:
                    add(
                        item,
                        mapped,
                        value.lstrip(),
                    )
                else:
                    item[mapped] = ns(value)

                continue

        choice_match = CHOICE_RE.match(
            stripped
        )

        if (
            choice_match
            and kind == "MCQ"
        ):
            letter, value = choice_match.groups()

            if (
                letter in item["choices"]
                and ns(value)
            ):
                item["choices"][letter] += (
                    "\n[DUPLICATE CHOICE]\n"
                    + value
                )

            elif letter not in item["choices"]:
                item["choices"][letter] = value

            field = None

            choice = (
                letter
                if ns(value)
                else None
            )

            continue

        if (
            choice
            and kind == "MCQ"
        ):
            item["choices"][choice] += (
                "\n" + stripped
            )
            continue

        if field:
            if field in MULTI:
                add(
                    item,
                    field,
                    stripped,
                )
            else:
                item[field] = ns(
                    item.get(field, "")
                    + " "
                    + stripped
                )

        else:
            add(
                item,
                "prompt",
                stripped,
            )
            field = "prompt"

    for key in [
        "unit",
        "primaryUnit",
        "secondaryUnit",
        "skill",

        "statisticalPracticesRaw",
        "primaryPracticesRaw",

        "stimulusId",

        "correct",
        "correctAnswerText",

        "frqType",
        "expectedPoints",
    ]:
        item[key] = ns(
            item.get(key, "")
        )

    for key in MULTI:
        item[key] = nm(
            item.get(key, "")
        )

    item["choices"] = {
        key: nm(value)
        for key, value
        in item["choices"].items()
    }

    return item


def parse_questions(text):
    lines = text.splitlines()
    starts = []

    for index, raw in enumerate(lines):
        match = ID_RE.fullmatch(
            raw.strip()
        )

        if not match:
            continue

        qid, kind, exam, number = (
            match.groups()
        )

        starts.append(
            (
                index,
                qid.upper(),
                kind.upper(),
                int(exam),
                int(number),
            )
        )

    output = []

    for position, start in enumerate(starts):
        index, qid, kind, exam, number = start

        if position + 1 < len(starts):
            end = starts[position + 1][0]
        else:
            end = len(lines)

        output.append(
            parse_block(
                qid,
                kind,
                exam,
                number,
                lines[index + 1:end],
            )
        )

    return output


def practices(raw):
    if not ns(raw):
        return []

    return sorted(
        {
            int(value)
            for value in re.findall(
                r"(?i)(?:practice\s*)?([1-4])\b",
                raw,
            )
        }
    )


def canonical_unit(raw):
    raw = ns(raw)

    if (
        not raw
        or raw.lower()
        in {"none", "n/a", "na"}
    ):
        return "", None

    match = re.search(
        r"(?i)\bunit\s*([0-9]+)\b",
        raw,
    )

    if not match:
        return (
            raw,
            f"invalid Unit label '{raw}'",
        )

    number = int(match.group(1))

    if number not in UNITS:
        return (
            raw,
            f"invalid Unit {number}; "
            "only Units 1-5 are valid",
        )

    return (
        f"Unit {number}: {UNITS[number]}",
        None,
    )


def metadata(item):
    errors = []
    qid = item["id"]

    for key in [
        "unit",
        "primaryUnit",
        "secondaryUnit",
    ]:
        item[key], error = canonical_unit(
            item.get(key, "")
        )

        if error:
            errors.append(
                f"{qid}: {key}: {error}"
            )

    pairs = [
        (
            "statisticalPracticesRaw",
            "statisticalPractices",
        ),
        (
            "primaryPracticesRaw",
            "primaryPractices",
        ),
    ]

    for raw_key, output_key in pairs:
        item[output_key] = practices(
            item.get(raw_key, "")
        )

        if (
            item.get(raw_key)
            and not item[output_key]
        ):
            errors.append(
                f"{qid}: cannot parse "
                f"{raw_key}; use "
                "Practice numbers 1-4"
            )

    if (
        not item["primaryPractices"]
        and item["statisticalPractices"]
    ):
        item["primaryPractices"] = (
            item["statisticalPractices"][:]
        )

    return errors


def expected_ids(
    kind,
    exam,
    count,
):
    return [
        f"APSTAT-{kind}{exam}-{number:03d}"
        for number in range(
            1,
            count + 1,
        )
    ]


def unique_errors(
    items,
    label,
):
    ids = [
        item["id"]
        for item in items
    ]

    duplicates = sorted(
        {
            qid
            for qid in ids
            if ids.count(qid) > 1
        }
    )

    if duplicates:
        return [
            f"{label}: duplicate IDs: "
            f"{duplicates}"
        ]

    return []


def propagate_sets(items):
    bank = {}

    for question in items:
        stimulus_id = ns(
            question.get(
                "stimulusId"
            )
        )

        if not stimulus_id:
            continue

        bank.setdefault(
            stimulus_id,
            {
                "stimulus": "",
                "dataset": "",
                "table": "",
            },
        )

        for field in [
            "stimulus",
            "dataset",
            "table",
        ]:
            if (
                question.get(field)
                and not bank[stimulus_id][field]
            ):
                bank[stimulus_id][field] = (
                    question[field]
                )

    for question in items:
        stimulus_id = ns(
            question.get(
                "stimulusId"
            )
        )

        if stimulus_id not in bank:
            continue

        for field in [
            "stimulus",
            "dataset",
            "table",
        ]:
            if not question.get(field):
                question[field] = (
                    bank[stimulus_id][field]
                )


def validate_mcq(
    items,
    answer_key,
    exam,
):
    label = f"MCQ Exam {exam:02d}"

    errors = unique_errors(
        items,
        label,
    )

    ids = [
        item["id"]
        for item in items
    ]

    expected = expected_ids(
        "MCQ",
        exam,
        42,
    )

    if len(items) != 42:
        errors.append(
            f"{label}: expected exactly "
            f"42 questions, found "
            f"{len(items)}"
        )

    if ids != expected:
        errors.append(
            f"{label}: IDs must run "
            f"exactly {expected[0]} "
            f"through {expected[-1]} "
            "in order"
        )

    if answer_key:
        missing = sorted(
            set(ids)
            - set(answer_key)
        )

        extra = sorted(
            set(answer_key)
            - set(ids)
        )

        if missing:
            errors.append(
                f"{label}: answer key "
                f"missing IDs: {missing}"
            )

        if extra:
            errors.append(
                f"{label}: answer key "
                f"has unexpected IDs: "
                f"{extra}"
            )

    for question in items:
        qid = question["id"]

        errors += metadata(
            question
        )

        if question["examNumber"] != exam:
            errors.append(
                f"{qid}: ID exam number "
                "does not match filename"
            )

        if not question["prompt"]:
            errors.append(
                f"{qid}: missing Prompt"
            )

        if (
            set(question["choices"])
            != {"A", "B", "C", "D"}
        ):
            errors.append(
                f"{qid}: must have "
                "exactly choices A-D; "
                f"found "
                f"{sorted(question['choices'])}"
            )

        for letter, value in (
            question["choices"].items()
        ):
            if not ns(value):
                errors.append(
                    f"{qid}: choice "
                    f"{letter} is empty"
                )

            if (
                "[DUPLICATE CHOICE]"
                in value
            ):
                errors.append(
                    f"{qid}: duplicate "
                    f"choice {letter}"
                )

        if (
            answer_key
            and qid in answer_key
        ):
            letter = (
                answer_key[qid]["correct"]
            )

            answer = (
                answer_key[qid]["answer"]
            )

            explanation = (
                answer_key[qid][
                    "explanation"
                ]
            )

        else:
            letter = ns(
                question["correct"]
            ).upper()

            answer = ns(
                question[
                    "correctAnswerText"
                ]
            )

            explanation = nm(
                question["explanation"]
            )

        if (
            letter not in "ABCD"
            or len(letter) != 1
        ):
            errors.append(
                f"{qid}: Correct must "
                "be exactly one of A-D"
            )
            continue

        if (
            letter
            not in question["choices"]
        ):
            errors.append(
                f"{qid}: correct answer "
                f"{letter} missing from "
                "choices"
            )
            continue

        selected = ns(
            question["choices"][letter]
        )

        if not answer:
            errors.append(
                f"{qid}: missing "
                "Correct Answer text"
            )

        elif ns(answer) != selected:
            errors.append(
                f"{qid}: Correct Answer "
                "text mismatch; choice "
                f"{letter} is "
                f"'{selected}', answer "
                f"text is '{answer}'"
            )

        if not explanation:
            errors.append(
                f"{qid}: Explanation "
                "is required"
            )

        question.update(
            {
                "correct": letter,
                "answer": letter,
                "correctAnswer": letter,
                "correctAnswerText": answer,
                "explanation": explanation,
                "credits": 1,
            }
        )

    propagate_sets(items)

    return errors


def derive_point_allocation(scoring_guide):
    rows = re.findall(
        r"(?im)^\s*(\([a-z]\))\s+(\d+)\s+points?\s*$",
        scoring_guide or "",
    )

    if not rows:
        return "", []

    parsed = [
        (label, int(points))
        for label, points in rows
    ]

    text = "\n".join(
        f"{label} {points} point{'s' if points != 1 else ''}"
        for label, points in parsed
    )

    return text, parsed


def validate_frq(
    items,
    exam,
):
    label = f"FRQ Exam {exam:02d}"

    errors = unique_errors(
        items,
        label,
    )

    ids = [
        item["id"]
        for item in items
    ]

    expected = expected_ids(
        "FRQ",
        exam,
        4,
    )

    if len(items) != 4:
        errors.append(
            f"{label}: expected exactly "
            f"4 FRQs, found {len(items)}"
        )

    if ids != expected:
        errors.append(
            f"{label}: IDs must run "
            f"exactly {expected[0]} "
            f"through {expected[-1]} "
            "in order"
        )

    structure = {
        1: {
            "type": "Multi-Focus",
            "practices": [1, 2],
        },
        2: {
            "type": "Multi-Focus",
            "practices": [3, 4],
        },
        3: {
            "type": "Inference",
            "practices": None,
        },
        4: {
            "type": "Multi-Focus",
            "practices": [2, 3, 4],
        },
    }

    for question in items:
        qid = question["id"]
        number = question["questionNumber"]

        errors += metadata(
            question
        )

        if question["examNumber"] != exam:
            errors.append(
                f"{qid}: ID exam number "
                "does not match filename"
            )

        if question["section"].upper() != "FRQ":
            errors.append(
                f"{qid}: Section must be FRQ"
            )

        if question["type"].lower() != "frq":
            errors.append(
                f"{qid}: Type must be frq"
            )

        if not question["prompt"]:
            errors.append(
                f"{qid}: missing Prompt"
            )

        if not question["scoringGuide"]:
            errors.append(
                f"{qid}: missing Scoring Guide"
            )

        if not (
            question["modelResponse"]
            or question["modelGuidance"]
        ):
            errors.append(
                f"{qid}: missing Model Response "
                "or Model Guidance"
            )

        expected_spec = structure.get(number)

        if expected_spec is None:
            errors.append(
                f"{qid}: unexpected FRQ number"
            )
            continue

        source_type = ns(
            question.get("frqType", "")
        )

        if not source_type:
            errors.append(
                f"{qid}: missing source FRQ Type"
            )

        if (
            number == 3
            and "inference" not in source_type.lower()
        ):
            errors.append(
                f"{qid}: FRQ 3 source type must "
                "identify statistical inference"
            )

        if (
            number in {1, 2, 4}
            and "inference" in source_type.lower()
        ):
            errors.append(
                f"{qid}: source FRQ Type conflicts "
                "with required Multi-Focus structure"
            )

        question["sourceFrqType"] = source_type
        question["frqType"] = expected_spec["type"]

        expected_practices = expected_spec["practices"]

        if expected_practices is not None:
            if question["primaryPractices"]:
                if question["primaryPractices"] != expected_practices:
                    errors.append(
                        f"{qid}: primary practices must be "
                        f"{expected_practices}; found "
                        f"{question['primaryPractices']}"
                    )
            else:
                question["primaryPractices"] = expected_practices[:]

            if not question["statisticalPractices"]:
                question["statisticalPractices"] = (
                    expected_practices[:]
                )

            question["primaryPracticesRaw"] = ", ".join(
                str(value)
                for value in expected_practices
            )

        try:
            points = int(
                ns(
                    question[
                        "expectedPoints"
                    ]
                )
            )

        except Exception:
            points = None

        if points != 10:
            errors.append(
                f"{qid}: Expected Points "
                "must be 10"
            )

        guide = question["scoringGuide"]

        total_match = re.search(
            r"(?im)^\s*Total Points:\s*(\d+)\s*$",
            guide,
        )

        if not total_match:
            errors.append(
                f"{qid}: Scoring Guide must contain "
                "'Total Points: 10'"
            )

        elif int(total_match.group(1)) != 10:
            errors.append(
                f"{qid}: Scoring Guide Total Points "
                f"must be 10, found "
                f"{total_match.group(1)}"
            )

        derived_allocation, allocation_rows = (
            derive_point_allocation(guide)
        )

        if not question["pointAllocation"]:
            question["pointAllocation"] = (
                derived_allocation
            )

        if not question["pointAllocation"]:
            errors.append(
                f"{qid}: missing Point Allocation "
                "and no per-part point allocation "
                "could be derived from Scoring Guide"
            )

        if allocation_rows:
            allocated_total = sum(
                points
                for _, points in allocation_rows
            )

            if allocated_total != 10:
                errors.append(
                    f"{qid}: per-part point allocation "
                    f"sums to {allocated_total}, not 10"
                )

        question["expectedPoints"] = 10
        question["points"] = 10
        question["credits"] = 10

        if (
            question["modelResponse"]
            and not question["modelGuidance"]
        ):
            question["modelGuidance"] = (
                question["modelResponse"]
            )

        if (
            question["modelGuidance"]
            and not question["modelResponse"]
        ):
            question["modelResponse"] = (
                question["modelGuidance"]
            )

    return errors


def validate(path):
    kind, exam = file_info(path)

    text = path.read_text(
        encoding="utf-8-sig"
    )

    text = strip_trailing_nonimport(text)

    if kind == "mcq":
        question_text, key_text = (
            split_key(text)
        )

        items = parse_questions(
            question_text
        )

        answer_key, bad = parse_key(
            key_text
        )

        if bad:
            raise ValueError(
                f"{path.name}: malformed "
                "answer-key lines:\n- "
                + "\n- ".join(bad)
            )

        errors = validate_mcq(
            items,
            answer_key,
            exam,
        )

    else:
        items = parse_questions(
            text
        )

        errors = validate_frq(
            items,
            exam,
        )

    if not items:
        raise ValueError(
            f"{path.name}: no APSTAT "
            "question IDs found"
        )

    wrong = [
        question["id"]
        for question in items
        if question["section"]
        != kind.upper()
    ]

    if wrong:
        errors.append(
            f"{path.name}: wrong "
            f"section IDs found: {wrong}"
        )

    if errors:
        raise ValueError(
            f"{path.name}: validation "
            "failed:\n- "
            + "\n- ".join(errors)
        )

    return {
        "path": path,
        "kind": kind,
        "exam": exam,
        "questions": items,
    }


def json_name(
    kind,
    exam,
):
    return (
        f"ap_statistics_{kind}_"
        f"exam_{exam:02d}.json"
    )


def pdf_name(
    kind,
    exam,
):
    return (
        f"ap_statistics_{kind}_"
        f"exam_{exam:02d}.pdf"
    )


def title(
    kind,
    exam,
):
    section = (
        "MCQ"
        if kind == "mcq"
        else "FRQ"
    )

    return (
        f"AP Statistics {section} "
        f"Practice Exam {exam:02d}"
    )


def write_json(result):
    OUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = OUT / json_name(
        result["kind"],
        result["exam"],
    )

    payload = {
        "examId": "ap-statistics",

        "title": title(
            result["kind"],
            result["exam"],
        ),

        "section": result["kind"],

        "examNumber": result["exam"],

        "framework":
            "Effective Fall 2026",

        "questions":
            result["questions"],
    }

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return path


def unicode_font():
    names = [
        "STIXTwoText-Regular.ttf",
        "STIXGeneral.ttf",
        "Arial Unicode.ttf",
        "Arial.ttf",
        "Times New Roman.ttf",
        "DejaVuSans.ttf",
    ]

    roots = [
        Path(
            "/System/Library/Fonts"
        ),

        Path(
            "/Library/Fonts"
        ),

        Path.home()
        / "Library/Fonts",
    ]

    for name in names:
        for root in roots:
            if not root.exists():
                continue

            hit = next(
                root.rglob(name),
                None,
            )

            if hit:
                return hit

    for root in roots:
        if not root.exists():
            continue

        hit = next(
            root.rglob("*.ttf"),
            None,
        )

        if hit:
            return hit

    raise RuntimeError(
        "No TrueType font found "
        "on macOS for Unicode PDF "
        "generation"
    )


def make_pdf(
    txt,
    target,
    kind,
    exam,
):
    try:
        from reportlab.lib.pagesizes import A4

        from reportlab.lib.styles import (
            ParagraphStyle,
            getSampleStyleSheet,
        )

        from reportlab.lib.units import mm

        from reportlab.pdfbase import (
            pdfmetrics,
        )

        from reportlab.pdfbase.ttfonts import (
            TTFont,
        )

        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
        )

    except ImportError as error:
        raise RuntimeError(
            "ReportLab missing. Install "
            "with: python3 -m pip "
            "install reportlab"
        ) from error

    font = unicode_font()

    pdfmetrics.registerFont(
        TTFont(
            "APStatsUnicode",
            str(font),
        )
    )

    document_title = title(
        kind,
        exam,
    )

    doc = SimpleDocTemplate(
        str(target),

        pagesize=A4,

        rightMargin=18 * mm,
        leftMargin=18 * mm,

        topMargin=18 * mm,
        bottomMargin=18 * mm,

        title=document_title,
    )

    stylesheet = (
        getSampleStyleSheet()
    )

    body = ParagraphStyle(
        "body",

        parent=stylesheet[
            "BodyText"
        ],

        fontName="APStatsUnicode",

        fontSize=10.5,
        leading=14,

        spaceAfter=1.5 * mm,
    )

    heading = ParagraphStyle(
        "heading",

        parent=body,

        fontSize=17,
        leading=21,

        spaceAfter=7 * mm,
    )

    id_style = ParagraphStyle(
        "qid",

        parent=body,

        fontSize=11.5,

        spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    )

    choice_style = ParagraphStyle(
        "choice",

        parent=body,

        leftIndent=6 * mm,
        firstLineIndent=-3 * mm,
    )

    story = [
        Paragraph(
            html.escape(
                document_title
            ),
            heading,
        ),

        Paragraph(
            html.escape(
                "Original independent "
                "AP Statistics practice "
                "material. Not affiliated "
                "with or endorsed by the "
                "College Board."
            ),
            body,
        ),

        Spacer(
            1,
            4 * mm,
        ),
    ]

    source_text = txt.read_text(
        encoding="utf-8-sig"
    )

    for raw in (
        source_text.splitlines()
    ):
        line = raw.rstrip()

        if not line:
            story.append(
                Spacer(
                    1,
                    2.5 * mm,
                )
            )
            continue

        escaped = (
            html.escape(line)
            .replace(
                "  ",
                "&nbsp;&nbsp;",
            )
        )

        if ID_RE.fullmatch(
            line.strip()
        ):
            style = id_style

        elif CHOICE_RE.match(
            line.strip()
        ):
            style = choice_style

        else:
            style = body

        story.append(
            Paragraph(
                escaped,
                style,
            )
        )

    def decorate(
        canvas,
        doc_object,
    ):
        canvas.saveState()

        canvas.setTitle(
            document_title
        )

        canvas.setAuthor(
            "Independent AP Statistics "
            "Practice"
        )

        canvas.setFont(
            "APStatsUnicode",
            8,
        )

        canvas.drawString(
            18 * mm,
            10 * mm,
            f"{document_title} — "
            f"Page {doc_object.page}",
        )

        canvas.restoreState()

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    doc.build(
        story,

        onFirstPage=decorate,
        onLaterPages=decorate,
    )


def normalize_pdf(
    source,
    target,
    kind,
    exam,
):
    try:
        from pypdf import (
            PdfReader,
            PdfWriter,
        )

    except ImportError as error:
        raise RuntimeError(
            "pypdf missing. Install "
            "with: python3 -m pip "
            "install pypdf"
        ) from error

    reader = PdfReader(
        str(source)
    )

    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    document_title = title(
        kind,
        exam,
    )

    writer.add_metadata(
        {
            "/Title":
                document_title,

            "/Author":
                "Independent AP Statistics "
                "Practice",

            "/Subject":
                document_title,
        }
    )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with target.open(
        "wb"
    ) as file:
        writer.write(file)


def audit_pdf(
    path,
    kind,
    exam,
):
    from pypdf import PdfReader

    reader = PdfReader(
        str(path)
    )

    if not reader.pages:
        raise ValueError(
            f"{path.name}: PDF "
            "has no pages"
        )

    internal_title = ns(
        (
            reader.metadata.title
            if reader.metadata
            else ""
        )
        or ""
    )

    expected_title = title(
        kind,
        exam,
    )

    if (
        internal_title
        != expected_title
    ):
        raise ValueError(
            f"{path.name}: internal "
            "title mismatch: "
            f"'{internal_title}'"
        )

    extracted = "\n".join(
        (
            page.extract_text()
            or ""
        )
        for page in reader.pages
    )

    if (
        "AP Statistics"
        not in extracted
    ):
        raise ValueError(
            f"{path.name}: "
            "AP Statistics title "
            "not found in extracted "
            "PDF text"
        )

    first_id = (
        f"APSTAT-{kind.upper()}"
        f"{exam}-001"
    )

    if first_id not in extracted:
        raise ValueError(
            f"{path.name}: first ID "
            f"{first_id} not found "
            "in extracted PDF text"
        )

    # Build forbidden legacy names dynamically so the repository-wide
    # residual scanner does not flag this safety check itself.
    legacy = [
        "AP " + "Chem" + "istry",
        "AP" + "CHEM",
        "ap_" + "chem" + "istry",
        "ap-" + "chem" + "istry",
    ]

    for old in legacy:
        if (
            old.lower()
            in extracted.lower()
        ):
            raise ValueError(
                f"{path.name}: "
                "legacy content found: "
                f"{old}"
            )


def sync_pdf(result):
    kind = result["kind"]
    exam = result["exam"]

    name = pdf_name(
        kind,
        exam,
    )

    source = PDF_SRC / name
    target = PDF_OUT / name

    if source.exists():
        normalize_pdf(
            source,
            target,
            kind,
            exam,
        )

        origin = "SOURCE PDF"

    else:
        make_pdf(
            result["path"],
            target,
            kind,
            exam,
        )

        origin = (
            "GENERATED FROM TXT"
        )

    audit_pdf(
        target,
        kind,
        exam,
    )

    return (
        target,
        origin,
    )


def update_config():
    cfg = json.loads(
        CONFIG.read_text(
            encoding="utf-8"
        )
    )

    sections = {
        section["id"]: section
        for section
        in cfg["sections"]
    }

    for kind in [
        "mcq",
        "frq",
    ]:
        pattern = re.compile(
            rf"^ap_statistics_"
            rf"{kind}_exam_"
            rf"(\d{{2}})\.json$"
        )

        files = []

        for path in OUT.glob(
            "*.json"
        ):
            match = pattern.fullmatch(
                path.name
            )

            if match:
                files.append(
                    (
                        int(
                            match.group(1)
                        ),
                        path.name,
                    )
                )

        sections[kind][
            "examFiles"
        ] = [
            name
            for _, name
            in sorted(files)
        ]

    entries = []

    for path in PDF_OUT.glob(
        "*.pdf"
    ):
        match = PDF_RE.fullmatch(
            path.name
        )

        if not match:
            continue

        kind = (
            match.group(1).lower()
        )

        exam = int(
            match.group(2)
        )

        printable = (
            (exam - 1) * 2
            + (
                1
                if kind == "mcq"
                else 2
            )
        )

        section = (
            "MCQ"
            if kind == "mcq"
            else "FRQ"
        )

        entries.append(
            (
                printable,

                {
                    "label":
                        "AP Statistics "
                        f"{section} "
                        "Practice Exam "
                        f"{printable:02d}",

                    "file":
                        path.name,
                },
            )
        )

    cfg["printables"] = [
        entry
        for _, entry
        in sorted(entries)
    ]

    CONFIG.write_text(
        json.dumps(
            cfg,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",

        encoding="utf-8",
    )


def report(
    path,
    message,
):
    PROBLEMS.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path = (
        PROBLEMS
        / f"{path.stem}.errors.txt"
    )

    report_path.write_text(
        message.rstrip()
        + "\n",

        encoding="utf-8",
    )

    return report_path


def source_files(arguments):
    SRC.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not arguments:
        return sorted(
            SRC.glob("*.txt")
        )

    output = []

    for raw in arguments:
        path = Path(
            raw
        ).expanduser()

        if not path.is_absolute():
            direct = ROOT / path
            inside_import = (
                SRC / path.name
            )

            if direct.exists():
                path = direct

            else:
                path = inside_import

        if not path.exists():
            raise FileNotFoundError(
                raw
            )

        output.append(
            path.resolve()
        )

    return sorted(
        set(output),
        key=lambda path:
            path.name,
    )


def self_test():
    mcq = []
    answer_key = {}

    for number in range(
        1,
        43,
    ):
        question = base_item(
            f"APSTAT-MCQ1-"
            f"{number:03d}",

            "MCQ",
            1,
            number,
        )

        question.update(
            {
                "unit":
                    "Unit 1",

                "statisticalPracticesRaw":
                    "Practice 3",

                "prompt":
                    f"Q{number}",

                "choices":
                    {
                        "A": "Correct",
                        "B": "B",
                        "C": "C",
                        "D": "D",
                    },
            }
        )

        mcq.append(
            question
        )

        answer_key[
            question["id"]
        ] = {
            "correct":
                "A",

            "answer":
                "Correct",

            "explanation":
                "Explanation",
        }

    errors = validate_mcq(
        mcq,
        answer_key,
        1,
    )

    if errors:
        raise AssertionError(
            "\n".join(errors)
        )

    frq = []

    specs = {
        1: (
            "Multi-Focus",
            "1,2",
        ),

        2: (
            "Multi-Focus",
            "3,4",
        ),

        3: (
            "Inference — "
            "Confidence Interval",
            "4",
        ),

        4: (
            "Multi-Focus",
            "2,3,4",
        ),
    }

    for number in range(
        1,
        5,
    ):
        question = base_item(
            f"APSTAT-FRQ1-"
            f"{number:03d}",

            "FRQ",
            1,
            number,
        )

        frq_type, practice = (
            specs[number]
        )

        question.update(
            {
                "unit":
                    "Unit 3",

                "primaryPracticesRaw":
                    practice,

                "prompt":
                    "Prompt",

                "frqType":
                    frq_type,

                "expectedPoints":
                    "10",

                "pointAllocation":
                    "10 total points",

                "scoringGuide":
                    "Total Points: 10\n(a) 10 points\nPoint 1: Scoring criteria",

                "modelResponse":
                    "Model response",
            }
        )

        frq.append(
            question
        )

    errors = validate_frq(
        frq,
        1,
    )

    if errors:
        raise AssertionError(
            "\n".join(errors)
        )

    print(
        "SELF-TEST: PASSED"
    )

    print(
        "MCQ: 42 | A-D | "
        "answer-text match | "
        "explanation required"
    )

    print(
        "FRQ: 4 | 10 points each | "
        "type/practices | "
        "scoring/model fields"
    )

    print(
        "FRAMEWORK: Units 1-5 | "
        "Practices 1-4"
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "files",
        nargs="*",
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
    )

    parser.add_argument(
        "--self-test",
        action="store_true",
    )

    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    if not CONFIG.exists():
        print(
            "ERROR: config missing",
            file=sys.stderr,
        )
        return 1

    try:
        paths = source_files(
            args.files
        )

    except Exception as error:
        print(
            "ERROR:",
            error,
            file=sys.stderr,
        )
        return 1

    if not paths:
        print(
            f"ERROR: no TXT files "
            f"in {SRC}",
            file=sys.stderr,
        )
        return 1

    print(
        "AP STATISTICS IMPORTER |",
        (
            "VALIDATE ONLY"
            if args.validate_only
            else "IMPORT"
        ),
    )

    results = []
    failures = []

    # IMPORTANT:
    # Validation is transactional.
    # No public JSON/PDF/config is
    # modified until ALL selected
    # source TXT files pass.
    for path in paths:
        try:
            result = validate(
                path
            )

            results.append(
                result
            )

            print(
                f"VALID | {path.name} | "
                f"{result['kind'].upper()} | "
                f"questions="
                f"{len(result['questions'])}"
            )

        except Exception as error:
            failures.append(
                (
                    path,
                    str(error),
                )
            )

            report_path = report(
                path,
                str(error),
            )

            print(
                f"INVALID | "
                f"{path.name}"
            )

            print(error)

            print(
                "PROBLEM REPORT |",
                report_path,
            )

    if failures:
        print()

        print(
            "IMPORT BLOCKED | "
            "No JSON, PDF, or config "
            "changes were made."
        )

        return 1

    for result in results:
        problem_path = (
            PROBLEMS
            / (
                f"{result['path'].stem}"
                ".errors.txt"
            )
        )

        if problem_path.exists():
            problem_path.unlink()

    print()

    print(
        "VALIDATION PASSED FOR "
        "ALL SELECTED FILES"
    )

    if args.validate_only:
        print(
            "No files imported "
            "(--validate-only)."
        )
        return 0

    for result in results:
        path = write_json(
            result
        )

        print(
            "JSON |",
            path.relative_to(
                ROOT
            ),
        )

    for result in results:
        path, origin = sync_pdf(
            result
        )

        print(
            "PDF  |",
            path.relative_to(
                ROOT
            ),
            "|",
            origin,
            "| AUDIT PASSED",
        )

    update_config()

    print(
        "CONFIG | updated"
    )

    print(
        "IMPORT COMPLETE | "
        f"exams={len(results)} | "
        f"JSON={len(results)} | "
        f"PDF={len(results)}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
