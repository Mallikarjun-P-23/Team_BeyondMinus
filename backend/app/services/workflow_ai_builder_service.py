"""
AI workflow builder service.

Turns natural language into a workflow graph (nodes + edges) that matches
existing workflow engine node types.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import settings
import app.services.postgres_service as db
from app.services.rejection_logger import log_workflow_rejection

logger = logging.getLogger(__name__)

_BLOCKS_CATALOG_PATH = (
    Path(__file__).resolve().parents[1] / "core" / "workflow_blocks_catalog.json"
)


def _load_workflow_blocks_catalog() -> dict[str, Any]:
    try:
        return json.loads(_BLOCKS_CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(
            f"Could not load workflow blocks catalog at {_BLOCKS_CATALOG_PATH}: {exc}"
        ) from exc


def _build_catalog_maps(catalog: dict[str, Any]) -> tuple[
    dict[str, tuple[str, str, str, dict[str, str]]],
    dict[str, tuple[str, ...]],
    dict[str, tuple[str, ...]],
    dict[str, tuple[str, ...]],
]:
    allowed_node_types: dict[str, tuple[str, str, str, dict[str, str]]] = {}
    trigger_keywords: dict[str, tuple[str, ...]] = {}
    output_keywords: dict[str, tuple[str, ...]] = {}
    node_keywords: dict[str, tuple[str, ...]] = {}

    for category in catalog.get("categories", []):
        if not isinstance(category, dict):
            continue

        react_flow_type = str(category.get("react_flow_type") or "").strip()
        if react_flow_type not in {"trigger", "action", "conditional", "endpoint"}:
            continue

        for node in category.get("nodes", []):
            if not isinstance(node, dict):
                continue

            node_type = str(node.get("nodeType") or "").strip()
            if not node_type:
                continue

            label = str(node.get("label") or node_type).strip() or node_type
            description = str(node.get("description") or "").strip()
            params = node.get("params") if isinstance(node.get("params"), dict) else {}
            keywords = tuple(
                str(keyword).strip().lower()
                for keyword in node.get("keywords", [])
                if str(keyword).strip()
            )

            allowed_node_types[node_type] = (react_flow_type, label, description, params)
            node_keywords[node_type] = keywords
            if react_flow_type == "trigger":
                trigger_keywords[node_type] = keywords
            if react_flow_type == "endpoint":
                output_keywords[node_type] = keywords

    return allowed_node_types, trigger_keywords, output_keywords, node_keywords


_BLOCKS_CATALOG = _load_workflow_blocks_catalog()

# nodeType -> (react_flow_type, default_label, default_description, default_params)
_ALLOWED_NODE_TYPES, _TRIGGER_KEYWORDS, _OUTPUT_KEYWORDS, _NODE_KEYWORDS = _build_catalog_maps(
    _BLOCKS_CATALOG
)

_TRIGGER_TYPES = {k for k, v in _ALLOWED_NODE_TYPES.items() if v[0] == "trigger"}
_OUTPUT_TYPES = {k for k, v in _ALLOWED_NODE_TYPES.items() if v[0] == "endpoint"}
_CONDITIONAL_TYPES = {k for k, v in _ALLOWED_NODE_TYPES.items() if v[0] == "conditional"}

_BUILDER_MAX_CLARIFICATION_TURNS = 3
_UNSUPPORTED_HINTS: dict[str, str] = {
    str(k).lower(): str(v)
    for k, v in (_BLOCKS_CATALOG.get("unsupported_hints") or {}).items()
    if str(k).strip() and str(v).strip()
}
_DEFAULT_TRIGGER_TYPE = str(
    (_BLOCKS_CATALOG.get("fallbacks") or {}).get("default_trigger")
    or "lab_results_received"
)
_DEFAULT_OUTPUT_TYPE = str(
    (_BLOCKS_CATALOG.get("fallbacks") or {}).get("default_output")
    or "log_completion"
)
_MIN_CONFIDENCE_SCORE = float(
    (_BLOCKS_CATALOG.get("confidence") or {}).get("min_score") or 0.55
)
_MEDICAL_KEYWORDS: tuple[str, ...] = tuple(
    str(keyword).strip().lower()
    for keyword in (_BLOCKS_CATALOG.get("medical_keywords") or [])
    if str(keyword).strip()
)

if not _ALLOWED_NODE_TYPES:
    raise RuntimeError("Workflow blocks catalog did not contain any usable node definitions")

if _DEFAULT_TRIGGER_TYPE not in _ALLOWED_NODE_TYPES:
    _DEFAULT_TRIGGER_TYPE = next(iter(_TRIGGER_TYPES), "")

if _DEFAULT_OUTPUT_TYPE not in _ALLOWED_NODE_TYPES:
    _DEFAULT_OUTPUT_TYPE = next(iter(_OUTPUT_TYPES), "")


class WorkflowBuilderError(RuntimeError):
    pass


def _new_node_id() -> str:
    return f"ai_{uuid4().hex[:12]}"


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()

    # Strip fenced markdown if present.
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\\s*", "", cleaned)
        cleaned = re.sub(r"\\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: capture first JSON object region.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


def _is_prompt_injection_attempt(prompt: str) -> bool:
    text = (prompt or "").lower()
    if not text:
        return False

    patterns = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"disregard\s+(all\s+)?(system|developer)\s+instructions",
        r"reveal\s+(the\s+)?(system|developer)\s+prompt",
        r"show\s+(the\s+)?(system|developer)\s+prompt",
        r"jailbreak",
        r"prompt\s+injection",
        r"bypass\s+(safety|guardrails|policy)",
        r"do\s+anything\s+now",
        r"act\s+as\s+.*(root|admin|developer)",
        r"return\s+raw\s+instructions",
    ]

    return any(re.search(p, text) for p in patterns)


def _empty_workflow_response() -> dict[str, Any]:
    # Intentionally silent/no explanation response for prompt-injection attempts.
    return {
        "workflow_name": "",
        "workflow_description": "",
        "nodes": [],
        "edges": [],
        "notes": [],
        "warnings": [],
    }


def _normalize_node(raw: dict[str, Any]) -> dict[str, Any] | None:
    node_type = str(raw.get("nodeType") or "").strip()
    if node_type not in _ALLOWED_NODE_TYPES:
        return None

    react_flow_type, default_label, default_description, default_params = _ALLOWED_NODE_TYPES[
        node_type
    ]

    label = str(raw.get("label") or default_label).strip() or default_label
    description = (
        str(raw.get("description") or default_description).strip() or default_description
    )

    raw_params = raw.get("params") if isinstance(raw.get("params"), dict) else {}
    # Strictly keep only cataloged params for the selected allowed nodeType.
    params = {**default_params}
    allowed_param_keys = set(default_params.keys())
    for key, value in raw_params.items():
        if value is None:
            continue
        key_s = str(key)
        if key_s not in allowed_param_keys:
            continue
        params[key_s] = str(value)

    node_id = str(raw.get("id") or "").strip() or _new_node_id()

    x = raw.get("position", {}).get("x", 0) if isinstance(raw.get("position"), dict) else 0
    y = raw.get("position", {}).get("y", 0) if isinstance(raw.get("position"), dict) else 0

    try:
        pos_x = float(x)
    except Exception:
        pos_x = 0.0
    try:
        pos_y = float(y)
    except Exception:
        pos_y = 0.0

    return {
        "id": node_id,
        "type": react_flow_type,
        "position": {"x": pos_x, "y": pos_y},
        "data": {
            "label": label,
            "nodeType": node_type,
            "description": description,
            "params": params,
        },
    }


def _normalize_edges(raw_edges: list[dict[str, Any]], valid_node_ids: set[str]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str | None]] = set()

    for idx, edge in enumerate(raw_edges):
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if source not in valid_node_ids or target not in valid_node_ids:
            continue
        source_handle = edge.get("sourceHandle")
        if source_handle is not None:
            source_handle = str(source_handle)

        dedupe_key = (source, target, source_handle)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        normalized.append(
            {
                "id": str(edge.get("id") or f"ai_edge_{idx}_{uuid4().hex[:6]}"),
                "source": source,
                "target": target,
                **({"sourceHandle": source_handle} if source_handle else {}),
                "animated": True,
                "style": {
                    "stroke": "#10b981" if source_handle == "true" else "#ef4444" if source_handle == "false" else "#C43B3B",
                    "strokeWidth": 2,
                },
            }
        )

    return normalized


def _auto_layout(nodes: list[dict[str, Any]]) -> None:
    lane_x = {
        "trigger": 120,
        "conditional": 340,
        "action": 560,
        "endpoint": 780,
    }
    lane_count = {"trigger": 0, "conditional": 0, "action": 0, "endpoint": 0}

    for node in nodes:
        node_type = node.get("type", "action")
        lane_count.setdefault(node_type, 0)
        index = lane_count[node_type]
        lane_count[node_type] += 1
        node["position"] = {"x": lane_x.get(node_type, 560), "y": 80 + index * 170}


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(k in text for k in keywords)


def _pick_best_type_from_prompt(
    user_prompt: str,
    available_types: set[str],
    keyword_map: dict[str, tuple[str, ...]],
    default_type: str,
) -> str:
    prompt_l = (user_prompt or "").lower()
    best_type = default_type
    best_score = -1
    for node_type in available_types:
        words = keyword_map.get(node_type, ())
        score = sum(1 for w in words if w in prompt_l)
        if score > best_score:
            best_score = score
            best_type = node_type
    return best_type


def _node_prompt_score(node: dict[str, Any], user_prompt: str) -> int:
    prompt_l = (user_prompt or "").lower()
    data = node.get("data", {})
    node_type = str(data.get("nodeType") or "")
    score = 0

    for w in _NODE_KEYWORDS.get(node_type, ()):
        if w in prompt_l:
            score += 2

    label = str(data.get("label") or "").lower()
    description = str(data.get("description") or "").lower()
    for token in re.findall(r"[a-z0-9_]+", prompt_l):
        if len(token) < 4:
            continue
        if token in label:
            score += 1
        if token in description:
            score += 1

    return score


def _make_edge(
    source: str,
    target: str,
    source_handle: str | None = None,
) -> dict[str, Any]:
    color = "#10b981" if source_handle == "true" else "#ef4444" if source_handle == "false" else "#C43B3B"
    edge: dict[str, Any] = {
        "id": f"ai_edge_{uuid4().hex[:6]}",
        "source": source,
        "target": target,
        "animated": True,
        "style": {"stroke": color, "strokeWidth": 2},
    }
    if source_handle:
        edge["sourceHandle"] = source_handle
    return edge


def _ensure_valid_flow(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    user_prompt: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []

    if not nodes:
        raise WorkflowBuilderError("AI did not generate any valid nodes")

    if len(nodes) > 30:
        nodes = nodes[:30]
        warnings.append("Workflow truncated to first 30 nodes for safety")

    trigger_nodes = [n for n in nodes if n.get("data", {}).get("nodeType") in _TRIGGER_TYPES]
    if not trigger_nodes:
        trigger_type = _pick_best_type_from_prompt(
            user_prompt,
            _TRIGGER_TYPES,
            _TRIGGER_KEYWORDS,
            _DEFAULT_TRIGGER_TYPE,
        )
        _, default_label, default_description, default_params = _ALLOWED_NODE_TYPES[trigger_type]
        trigger_id = _new_node_id()
        nodes.insert(
            0,
            {
                "id": trigger_id,
                "type": "trigger",
                "position": {"x": 120, "y": 80},
                "data": {
                    "label": default_label,
                    "nodeType": trigger_type,
                    "description": default_description,
                    "params": default_params,
                },
            },
        )
        warnings.append("No trigger was produced, inserted a default trigger")
        trigger_nodes = [nodes[0]]

    if len(trigger_nodes) > 1:
        preferred_trigger_type = _pick_best_type_from_prompt(
            user_prompt,
            {str(n.get("data", {}).get("nodeType") or "") for n in trigger_nodes},
            _TRIGGER_KEYWORDS,
            str(trigger_nodes[0].get("data", {}).get("nodeType") or _DEFAULT_TRIGGER_TYPE),
        )
        primary_trigger = next(
            (n for n in trigger_nodes if n.get("data", {}).get("nodeType") == preferred_trigger_type),
            trigger_nodes[0],
        )
        removed_ids = {n["id"] for n in trigger_nodes if n["id"] != primary_trigger["id"]}
        nodes = [n for n in nodes if n["id"] not in removed_ids]
        edges = [e for e in edges if e.get("source") not in removed_ids and e.get("target") not in removed_ids]
        warnings.append("Multiple triggers detected; kept one trigger aligned to the prompt")
        trigger_nodes = [primary_trigger]

    output_nodes = [n for n in nodes if n.get("data", {}).get("nodeType") in _OUTPUT_TYPES]
    if not output_nodes:
        output_type = _pick_best_type_from_prompt(
            user_prompt,
            _OUTPUT_TYPES,
            _OUTPUT_KEYWORDS,
            _DEFAULT_OUTPUT_TYPE,
        )
        _, default_label, default_description, default_params = _ALLOWED_NODE_TYPES[output_type]
        out_id = _new_node_id()
        nodes.append(
            {
                "id": out_id,
                "type": "endpoint",
                "position": {"x": 780, "y": 80},
                "data": {
                    "label": default_label,
                    "nodeType": output_type,
                    "description": default_description,
                    "params": default_params,
                },
            }
        )
        warnings.append("No output was produced, appended log completion node")
        output_nodes = [nodes[-1]]

    if len(output_nodes) > 1:
        preferred_output_type = _pick_best_type_from_prompt(
            user_prompt,
            {str(n.get("data", {}).get("nodeType") or "") for n in output_nodes},
            _OUTPUT_KEYWORDS,
            str(output_nodes[0].get("data", {}).get("nodeType") or _DEFAULT_OUTPUT_TYPE),
        )
        primary_output = next(
            (n for n in output_nodes if n.get("data", {}).get("nodeType") == preferred_output_type),
            output_nodes[0],
        )
        removed_ids = {n["id"] for n in output_nodes if n["id"] != primary_output["id"]}
        nodes = [n for n in nodes if n["id"] not in removed_ids]
        edges = [e for e in edges if e.get("source") not in removed_ids and e.get("target") not in removed_ids]
        warnings.append("Multiple outputs detected; kept one output aligned to the prompt")
        output_nodes = [primary_output]

    valid_ids = {n["id"] for n in nodes}
    _ = _normalize_edges(edges, valid_ids)

    trigger_node = trigger_nodes[0]
    output_node = output_nodes[0]

    non_terminal_nodes = [
        n for n in nodes if n["id"] not in {trigger_node["id"], output_node["id"]}
    ]

    original_index = {n["id"]: i for i, n in enumerate(nodes)}
    pipeline_nodes = sorted(
        non_terminal_nodes,
        key=lambda n: (
            {"conditional": 0, "action": 1}.get(n.get("type", "action"), 2),
            -_node_prompt_score(n, user_prompt),
            original_index.get(n["id"], 0),
        ),
    )

    rebuilt_edges: list[dict[str, Any]] = []
    if not pipeline_nodes:
        rebuilt_edges.append(_make_edge(trigger_node["id"], output_node["id"]))
    else:
        rebuilt_edges.append(_make_edge(trigger_node["id"], pipeline_nodes[0]["id"]))
        for idx, node in enumerate(pipeline_nodes):
            next_target = (
                pipeline_nodes[idx + 1]["id"] if idx + 1 < len(pipeline_nodes) else output_node["id"]
            )
            node_type = str(node.get("data", {}).get("nodeType") or "")
            if node_type in _CONDITIONAL_TYPES:
                rebuilt_edges.append(_make_edge(node["id"], next_target, "true"))
                rebuilt_edges.append(_make_edge(node["id"], output_node["id"], "false"))
            else:
                rebuilt_edges.append(_make_edge(node["id"], next_target))

    edges = _normalize_edges(rebuilt_edges, valid_ids)
    warnings.append("Rebuilt edges into one connected workflow path aligned to prompt intent")

    _auto_layout(nodes)
    return nodes, edges, warnings


def _fallback_workflow(user_prompt: str) -> dict[str, Any]:
    trigger_type = _DEFAULT_TRIGGER_TYPE
    output_type = _DEFAULT_OUTPUT_TYPE
    trigger_spec = _ALLOWED_NODE_TYPES.get(trigger_type)
    output_spec = _ALLOWED_NODE_TYPES.get(output_type)
    if trigger_spec is None or output_spec is None:
        raise WorkflowBuilderError("Workflow catalog defaults are not configured correctly")

    trigger = {
        "id": _new_node_id(),
        "type": trigger_spec[0],
        "position": {"x": 120, "y": 80},
        "data": {
            "label": trigger_spec[1],
            "nodeType": trigger_type,
            "description": trigger_spec[2],
            "params": trigger_spec[3],
        },
    }
    action = {
        "id": _new_node_id(),
        "type": "action",
        "position": {"x": 560, "y": 80},
        "data": {
            "label": "Send Notification",
            "nodeType": "send_notification",
            "description": "Notify staff for manual review",
            "params": {
                "message": f"AI fallback generated from request: {user_prompt[:120]}",
                "recipient": "staff",
                "priority": "normal",
            },
        },
    }
    output = {
        "id": _new_node_id(),
        "type": output_spec[0],
        "position": {"x": 780, "y": 80},
        "data": {
            "label": output_spec[1],
            "nodeType": output_type,
            "description": output_spec[2],
            "params": output_spec[3],
        },
    }

    nodes = [trigger, action, output]
    edges = [
        {
            "id": f"ai_edge_{uuid4().hex[:6]}",
            "source": trigger["id"],
            "target": action["id"],
            "animated": True,
            "style": {"stroke": "#C43B3B", "strokeWidth": 2},
        },
        {
            "id": f"ai_edge_{uuid4().hex[:6]}",
            "source": action["id"],
            "target": output["id"],
            "animated": True,
            "style": {"stroke": "#C43B3B", "strokeWidth": 2},
        },
    ]

    return {
        "workflow_name": "AI Generated Workflow",
        "workflow_description": "Fallback workflow generated when AI response was unavailable.",
        "nodes": nodes,
        "edges": edges,
        "warnings": ["Used fallback generator because AI model response failed"],
    }


def _coerce_history_messages(conversation_history: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for message in conversation_history or []:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "").strip().lower()
        content = str(message.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        messages.append({"role": role, "content": content})
    return messages


def _combined_conversation_text(
    user_prompt: str, conversation_history: list[dict[str, str]]
) -> str:
    parts: list[str] = []
    for message in conversation_history:
        parts.append(f"{message['role']}: {message['content']}")
    if user_prompt.strip():
        parts.append(f"user: {user_prompt.strip()}")
    return "\n".join(parts)


def _combined_user_text(
    user_prompt: str, conversation_history: list[dict[str, str]]
) -> str:
    parts = [message["content"] for message in conversation_history if message["role"] == "user"]
    if user_prompt.strip():
        parts.append(user_prompt.strip())
    return "\n".join(parts)


def _best_keyword_match(text: str, keyword_map: dict[str, tuple[str, ...]]) -> str | None:
    best_type: str | None = None
    best_score = 0
    for candidate_type, keywords in keyword_map.items():
        score = sum(1 for keyword in keywords if keyword in text)
        if score > best_score:
            best_score = score
            best_type = candidate_type
    return best_type


def _count_keyword_hits(text: str, keyword_map: dict[str, tuple[str, ...]]) -> int:
    return sum(1 for keywords in keyword_map.values() for keyword in keywords if keyword in text)


def _intent_signal_count(text: str) -> int:
    return len(
        re.findall(
            r"\b(build|create|workflow|trigger|then|if|else|when|send|call|notify|schedule|check|report|log)\b",
            text,
        )
    )


def _is_medical_prompt(text: str) -> bool:
    prompt_l = (text or "").lower()
    if not prompt_l.strip():
        return False

    for keyword in _MEDICAL_KEYWORDS:
        if keyword and keyword in prompt_l:
            return True

    if any(keyword in prompt_l for keyword in _UNSUPPORTED_HINTS.keys()):
        return True

    if _count_keyword_hits(prompt_l, _NODE_KEYWORDS) > 0:
        return True

    return False

def _extract_builder_context(text: str) -> dict[str, Any]:
    prompt_l = text.lower()
    trigger = _best_keyword_match(prompt_l, _TRIGGER_KEYWORDS)
    action = _best_keyword_match(
        prompt_l,
        {
            node_type: keywords
            for node_type, keywords in _NODE_KEYWORDS.items()
            if _ALLOWED_NODE_TYPES.get(node_type, (None,))[0] == "action"
        },
    )
    condition = _best_keyword_match(
        prompt_l,
        {
            node_type: keywords
            for node_type, keywords in _NODE_KEYWORDS.items()
            if _ALLOWED_NODE_TYPES.get(node_type, (None,))[0] == "conditional"
        },
    )
    output = _best_keyword_match(prompt_l, _OUTPUT_KEYWORDS)

    wants_branching = bool(
        re.search(
            r"\b(if|when|otherwise|else|branch|threshold|greater than|less than|abnormal|normal)\b",
            prompt_l,
        )
    )

    unsupported_reasons = [
        reason for hint, reason in _UNSUPPORTED_HINTS.items() if hint in prompt_l
    ]

    keyword_hits = _count_keyword_hits(prompt_l, _NODE_KEYWORDS)
    intent_signals = _intent_signal_count(prompt_l)
    token_count = len(re.findall(r"[a-z0-9]+", prompt_l))
    is_unclear = token_count < 4 or (keyword_hits == 0 and intent_signals == 0)

    if action is None:
        action = _best_keyword_match(
            prompt_l,
            {
                node_type: keywords
                for node_type, keywords in _NODE_KEYWORDS.items()
                if _ALLOWED_NODE_TYPES.get(node_type, (None,))[0] == "action"
                and any(keyword in prompt_l for keyword in keywords)
            },
        )

    return {
        "trigger": trigger,
        "action": action,
        "condition": condition,
        "output": output,
        "wants_branching": wants_branching,
        "unsupported_reasons": unsupported_reasons,
        "keyword_hits": keyword_hits,
        "intent_signals": intent_signals,
        "is_unclear": is_unclear,
    }


def _builder_confidence_score(context: dict[str, Any]) -> float:
    required_slots = 3 + (1 if context.get("wants_branching") else 0)
    matched_slots = 0
    if context.get("trigger"):
        matched_slots += 1
    if context.get("action"):
        matched_slots += 1
    if context.get("output"):
        matched_slots += 1
    if context.get("wants_branching"):
        if context.get("condition"):
            matched_slots += 1

    coverage = matched_slots / max(required_slots, 1)
    keyword_signal = min(float(context.get("keyword_hits") or 0) / 4.0, 1.0)
    intent_signal = min(float(context.get("intent_signals") or 0) / 2.0, 1.0)
    base_score = (0.55 * coverage) + (0.25 * keyword_signal) + (0.20 * intent_signal)
    if context.get("is_unclear"):
        base_score *= 0.3
    return round(base_score, 3)


def _clarification_questions(context: dict[str, Any]) -> list[str]:
    questions: list[str] = []

    if not context.get("trigger"):
        questions.append("What event should trigger this workflow?")
    if not context.get("action"):
        questions.append("What should the workflow do after it is triggered?")
    if context.get("wants_branching") and not context.get("condition"):
        questions.append("If this needs branching, what rule or threshold should decide it?")
    if not context.get("output"):
        questions.append("What should the final outcome be, such as SMS, call, appointment, or log?")

    return questions[:3]


def _can_build_from_blocks(context: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    unsupported_reasons = list(context.get("unsupported_reasons") or [])
    if unsupported_reasons:
        return False, [], unsupported_reasons

    missing: list[str] = []
    if not context.get("trigger"):
        missing.append("trigger")
    if not context.get("action"):
        missing.append("action")
    if context.get("wants_branching") and not context.get("condition"):
        missing.append("branching rule")
    if not context.get("output"):
        missing.append("output")

    return True, missing, []


def _builder_decline_response(
    *,
    doctor_id: str | None,
    user_prompt: str,
    reason: str,
    missing_context: list[str],
    clarification_turns: int,
    audit_level: str = "error",
    assistant_message: str = "I cannot build this workflow with the current blocks.",
) -> dict[str, Any]:
    audit_log_id: str | None = None
    
    # Log rejection to universal text file for developer review
    rejection_id = log_workflow_rejection(
        doctor_id=doctor_id,
        user_prompt=user_prompt,
        rejection_reason=reason,
        rejection_message=assistant_message,
        missing_context=missing_context,
        clarification_turns=clarification_turns,
        additional_info={
            "audit_level": audit_level,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )
    
    try:
        log_row = db.create_call_log(
            {
                "doctor_id": doctor_id,
                "trigger_node": "workflow_builder",
                "status": "failed",
                "outcome": "declined",
                "execution_log": [
                    {
                        "node_type": "workflow_builder",
                        "label": "Agent Builder",
                        "status": "error",
                        "message": reason,
                        "metadata": {
                            "prompt": user_prompt,
                            "missing_context": missing_context,
                            "clarification_turns": clarification_turns,
                            "rejection_id": rejection_id,
                        },
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                ],
            }
        )
        audit_log_id = str(log_row.get("id") or "") or None
    except Exception as exc:
        logger.warning("Could not write workflow builder audit decline: %s", exc)

    return {
        "status": "declined",
        "assistant_message": assistant_message,
        "questions": [],
        "missing_context": missing_context,
        "can_build": False,
        "declined_reason": reason,
        "audit_log_id": audit_log_id,
        "rejection_id": rejection_id,  # Add rejection ID to response
        "workflow_name": "",
        "workflow_description": "",
        "nodes": [],
        "edges": [],
        "notes": [],
        "warnings": [reason],
    }


def _builder_clarification_response(
    *,
    questions: list[str],
    missing_context: list[str],
    clarification_turns: int,
    assistant_message: str | None = None,
) -> dict[str, Any]:
    lead_in = assistant_message or "I can build this, but I need a bit more context first."
    if clarification_turns > 0:
        lead_in = assistant_message or "I still need a bit more context to make this precise."

    return {
        "status": "needs_context",
        "assistant_message": lead_in,
        "questions": questions,
        "missing_context": missing_context,
        "can_build": True,
        "declined_reason": None,
        "audit_log_id": None,
        "workflow_name": "",
        "workflow_description": "",
        "nodes": [],
        "edges": [],
        "notes": [],
        "warnings": [],
    }


async def generate_workflow_from_natural_language(
    *,
    prompt: str,
    doctor_id: str | None = None,
    conversation_history: list[dict[str, Any]] | None = None,
    clarification_turns: int = 0,
) -> dict[str, Any]:
    user_prompt = (prompt or "").strip()
    if not user_prompt:
        raise WorkflowBuilderError("Prompt cannot be empty")

    if _is_prompt_injection_attempt(user_prompt):
        return {
            "status": "declined",
            "assistant_message": "",
            "questions": [],
            "missing_context": [],
            "can_build": False,
            "declined_reason": "The request could not be processed.",
            "audit_log_id": None,
            **_empty_workflow_response(),
        }

    history = _coerce_history_messages(conversation_history)
    user_text = _combined_user_text(user_prompt, history)
    combined_text = user_text
    context = _extract_builder_context(combined_text)
    confidence_score = _builder_confidence_score(context)

    if not _is_medical_prompt(user_text):
        return _builder_decline_response(
            doctor_id=doctor_id,
            user_prompt=user_prompt,
            reason="Request is not related to a medical workflow.",
            missing_context=[],
            clarification_turns=clarification_turns,
            assistant_message="I can't help with that because it doesn't look like a medical workflow request.",
        )

    if context.get("is_unclear"):
        if clarification_turns < _BUILDER_MAX_CLARIFICATION_TURNS:
            return _builder_clarification_response(
                questions=[
                    "Which event should trigger this workflow, and what should happen next?",
                ],
                missing_context=["trigger", "action", "output"],
                clarification_turns=clarification_turns,
                assistant_message="I need a little more detail to map this to the available workflow blocks.",
            )
        return _builder_decline_response(
            doctor_id=doctor_id,
            user_prompt=user_prompt,
            reason="Prompt did not contain enough meaningful workflow intent or recognizable block references.",
            missing_context=["trigger", "action", "output"],
            clarification_turns=clarification_turns,
            assistant_message="Sorry, I didn't understand that request well enough to build a safe workflow.",
        )

    supported_by_blocks, missing_context, unsupported_reasons = _can_build_from_blocks(context)
    if not supported_by_blocks:
        reason = "; ".join(unsupported_reasons) if unsupported_reasons else "Requested workflow uses blocks that are not available."
        return _builder_decline_response(
            doctor_id=doctor_id,
            user_prompt=user_prompt,
            reason=reason,
            missing_context=missing_context,
            clarification_turns=clarification_turns,
            assistant_message="I can't help you with this request using the currently available workflow blocks.",
        )

    questions = _clarification_questions(context)
    if questions and clarification_turns < _BUILDER_MAX_CLARIFICATION_TURNS:
        return _builder_clarification_response(
            questions=questions,
            missing_context=missing_context,
            clarification_turns=clarification_turns,
        )

    if questions and clarification_turns >= _BUILDER_MAX_CLARIFICATION_TURNS:
        reason = (
            "I still do not have enough context after multiple clarification turns to build a safe workflow."
        )
        return _builder_decline_response(
            doctor_id=doctor_id,
            user_prompt=user_prompt,
            reason=reason,
            missing_context=missing_context,
            clarification_turns=clarification_turns,
            assistant_message="I can't help with this safely because I still don't have enough usable context.",
        )

    if confidence_score < _MIN_CONFIDENCE_SCORE:
        if clarification_turns < _BUILDER_MAX_CLARIFICATION_TURNS:
            return _builder_clarification_response(
                questions=[
                    "Please restate this as: trigger event, then action, then expected outcome.",
                ],
                missing_context=missing_context or ["clear workflow intent"],
                clarification_turns=clarification_turns,
                assistant_message="I am not confident enough to build this workflow yet.",
            )
        return _builder_decline_response(
            doctor_id=doctor_id,
            user_prompt=user_prompt,
            reason=f"Confidence score {confidence_score} is below required threshold {_MIN_CONFIDENCE_SCORE}.",
            missing_context=missing_context or ["clear workflow intent"],
            clarification_turns=clarification_turns,
            assistant_message="Sorry, I didn't understand this request clearly enough to build a safe workflow.",
        )

    api_key = settings.openrouter_api_key.strip()
    model = settings.openrouter_model.strip() or "deepseek/deepseek-v3.2"
    base_url = settings.openrouter_base_url.rstrip("/")

    if not api_key:
        raise WorkflowBuilderError("OpenRouter API key is not configured")

    # system_prompt = (
    #     "You are an expert medical workflow graph planner. "
    #     "Convert doctor requests into an executable workflow graph for React Flow. "
    #     "Understand intent from full natural-language details, not just exact keywords. "
    #     "If user provides step-by-step workflow details, preserve that sequence in the generated nodes. "
    #     "Map synonyms and paraphrases to the closest allowed node types while keeping medical logic coherent. "
    #     "Never invent custom triggers, conditionals, actions, outputs, or nodeType values. "
    #     "If a requested step is not available, map it to the closest allowed node type. "
    #     "Generate exactly one coherent workflow graph where every node is connected to the same flow. "
    #     "Use exactly one trigger node and one output node. "
    #     "Output JSON only with these keys: "
    #     "workflow_name (string), workflow_description (string), nodes (array), edges (array), notes (array of strings). "
    #     "Each node must include: id, nodeType, label, description, params. "
    #     "Allowed nodeType values are exactly: "
    #     + ", ".join(sorted(_ALLOWED_NODE_TYPES.keys()))
    #     + ". "
    #     "Each edge must include source and target; for conditional branches, set sourceHandle to true or false. "
    #     "Do not include any markdown, explanation, or text outside JSON."
    # )

    system_prompt = (
    "You are an expert medical workflow graph planner. "
    "Your task is to convert doctor requests into a valid, executable workflow graph for React Flow. "

    "STRICT OUTPUT RULES: "
    "Return ONLY valid JSON. Do NOT include markdown, explanations, comments, or any text outside the JSON. "
    "The response must be directly parseable using JSON.parse(). "

    "FLOW CONSTRAINTS: "
    "Generate ONLY workflows that can be fully constructed using the provided allowed node types. "
    "DO NOT include any step, logic, or concept that cannot be implemented using the available nodes. "
    "If a requested step is not supported, you MUST map it to the closest valid nodeType from the allowed list. "
    "DO NOT invent or assume any new triggers, actions, conditionals, outputs, or nodeType values. "

    "STRUCTURE RULES: "
    "Generate exactly ONE coherent workflow graph. "
    "All nodes must be connected in a single valid flow (no isolated nodes). "
    "Use exactly ONE trigger node and exactly ONE output node. "
    "Preserve user-provided step order when explicitly given. "
    "Infer intent from natural language and map synonyms to valid node types while maintaining medical correctness. "

    "OUTPUT FORMAT (STRICT): "
    "Return JSON with EXACTLY these keys: "
    "workflow_name (string), workflow_description (string), nodes (array), edges (array), notes (array of strings). "

    "NODE RULES: "
    "Each node must include: id, nodeType, label, description, params. "
    "nodeType must be one of the allowed values only. "

    "EDGE RULES: "
    "Each edge must include: source and target. "
    "For conditional branching, include sourceHandle with value 'true' or 'false'. "

    "ALLOWED NODE TYPES: "
    + ", ".join(sorted(_ALLOWED_NODE_TYPES.keys())) + "."
    )

    user_context = {
        "doctor_id": doctor_id,
        "request": user_prompt,
        "conversation_history": history,
        "context_profile": context,
        "constraints": {
            "max_nodes": 12,
            "must_include_trigger": True,
            "must_include_output": True,
        },
    }

    payload = {
        "model": model,
        "temperature": 0.15,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_context)},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except Exception as exc:
        logger.exception("OpenRouter request failed")
        return {
            "status": "ready",
            "assistant_message": "I drafted a safe fallback workflow because the model request failed.",
            "questions": [],
            "missing_context": [],
            "can_build": True,
            "declined_reason": None,
            "audit_log_id": None,
            **(_fallback_workflow(user_prompt) | {"warnings": [f"OpenRouter request failed: {exc}"]}),
        }

    if response.status_code >= 400:
        detail = response.text[:500]
        logger.error(
            "OpenRouter generation failed status=%s detail=%s",
            response.status_code,
            detail,
        )
        return {
            "status": "ready",
            "assistant_message": "I drafted a safe fallback workflow because the model returned an error.",
            "questions": [],
            "missing_context": [],
            "can_build": True,
            "declined_reason": None,
            "audit_log_id": None,
            **(
                _fallback_workflow(user_prompt)
                | {
                    "warnings": [
                        f"OpenRouter returned {response.status_code}, used fallback workflow"
                    ]
                }
            ),
        }

    try:
        body = response.json()
        content = (
            body.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = _extract_json(content)

        raw_nodes = parsed.get("nodes") if isinstance(parsed.get("nodes"), list) else []
        raw_edges = parsed.get("edges") if isinstance(parsed.get("edges"), list) else []

        nodes: list[dict[str, Any]] = []
        for raw in raw_nodes:
            if not isinstance(raw, dict):
                continue
            normalized = _normalize_node(raw)
            if normalized is not None:
                nodes.append(normalized)

        # Deduplicate node ids
        seen_node_ids: set[str] = set()
        for node in nodes:
            node_id = node["id"]
            if node_id in seen_node_ids:
                node["id"] = _new_node_id()
            seen_node_ids.add(node["id"])

        edges = [e for e in raw_edges if isinstance(e, dict)]
        nodes, edges, validation_warnings = _ensure_valid_flow(
            nodes,
            edges,
            user_prompt,
        )

        ai_notes = parsed.get("notes") if isinstance(parsed.get("notes"), list) else []
        notes = [str(n) for n in ai_notes[:8]]

        workflow_name = str(parsed.get("workflow_name") or "AI Generated Workflow").strip()
        workflow_description = str(
            parsed.get("workflow_description")
            or f"Generated from doctor request: {user_prompt[:140]}"
        ).strip()

        return {
            "status": "ready",
            "assistant_message": "I am confident this workflow can be built with the available blocks.",
            "questions": [],
            "missing_context": [],
            "can_build": True,
            "declined_reason": None,
            "audit_log_id": None,
            "workflow_name": workflow_name,
            "workflow_description": workflow_description,
            "nodes": nodes,
            "edges": edges,
            "notes": notes,
            "warnings": validation_warnings,
        }
    except Exception as exc:
        logger.exception("Failed to parse OpenRouter response")
        return {
            "status": "ready",
            "assistant_message": "I drafted a safe fallback workflow because the AI response could not be parsed.",
            "questions": [],
            "missing_context": [],
            "can_build": True,
            "declined_reason": None,
            "audit_log_id": None,
            **(_fallback_workflow(user_prompt) | {"warnings": [f"AI response parsing failed: {exc}"]}),
        }
