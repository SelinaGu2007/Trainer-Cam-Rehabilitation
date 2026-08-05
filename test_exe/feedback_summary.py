"""Turn a technical assessment report into concise user-facing feedback."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


SUMMARY_FORMAT = "trainercam.feedback-summary"
SUMMARY_SCHEMA_VERSION = 1
SUPPORTED_LOCALES = ("en-US", "zh-CN")


class FeedbackSummaryError(ValueError):
    pass


_TEXT = {
    "en-US": {
        "excellent": ("excellent", "Excellent consistency"),
        "good": ("good", "Good overall movement"),
        "practice": ("practice", "Keep practising the key corrections"),
        "review": ("review", "Review the movement before repeating"),
        "score": "Your movement score is {score} out of 100.",
        "focus": "Focus on {labels}.",
        "no_focus": "No persistent movement issue crossed the configured feedback threshold.",
        "quality": "Some tracking or joint data was incomplete; interpret this result with care.",
        "disclaimer": "Engineering guidance only. This result is not a diagnosis and does not replace a rehabilitation professional.",
    },
    "zh-CN": {
        "excellent": ("excellent", "动作一致性很好"),
        "good": ("good", "整体动作完成良好"),
        "practice": ("practice", "请继续练习重点纠正项目"),
        "review": ("review", "建议复习动作后再继续训练"),
        "score": "本次动作得分为一百分中的 {score} 分。",
        "focus": "请重点检查：{labels}。",
        "no_focus": "没有持续性动作问题超过当前配置的提示阈值。",
        "quality": "部分人体跟踪或关节数据不完整，请谨慎理解本次结果。",
        "disclaimer": "本结果仅为工程辅助信息，不构成医疗诊断，也不能替代康复专业人员。",
    },
}


def _created_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _rating(score: float) -> str:
    if score >= 90:
        return "excellent"
    if score >= 75:
        return "good"
    if score >= 60:
        return "practice"
    return "review"


def _quality_needs_caution(report: Dict[str, Any]) -> bool:
    for role in ("tutor", "customer"):
        quality = report.get("quality", {}).get(role, {})
        if float(quality.get("required_joint_coverage", 1.0)) < 0.95:
            return True
        tracking = quality.get("subject_tracking", {})
        if not tracking.get("gate_passed", True) or tracking.get("warnings"):
            return True
    return False


def create_feedback_summary(
    report: Dict[str, Any], locale: str = "en-US"
) -> Dict[str, Any]:
    if report.get("format") != "trainercam.assessment-report":
        raise FeedbackSummaryError("Expected a TrainerCam assessment report")
    if report.get("schema_version") != 1:
        raise FeedbackSummaryError("Unsupported assessment report version")
    if locale not in SUPPORTED_LOCALES:
        raise FeedbackSummaryError(
            f"Unsupported feedback locale {locale!r}; use one of {SUPPORTED_LOCALES}"
        )
    try:
        score = float(report["overall_score"])
    except (KeyError, TypeError, ValueError) as exc:
        raise FeedbackSummaryError("Assessment report has no numeric overall score") from exc
    if not 0.0 <= score <= 100.0:
        raise FeedbackSummaryError("Assessment score must be between 0 and 100")

    text = _TEXT[locale]
    rating_key = _rating(score)
    rating_id, headline = text[rating_key]
    improvements = []
    for value in report.get("improvements", [])[:3]:
        feature_id = str(value.get("feature_id", "")).strip()
        label = str(value.get("label", feature_id)).strip()
        message = str(value.get("message", "")).strip()
        if feature_id and label:
            improvements.append(
                {"feature_id": feature_id, "label": label, "message": message}
            )

    rounded_score = round(score, 1)
    score_text = text["score"].format(score=f"{rounded_score:g}")
    if improvements:
        separator = "、" if locale == "zh-CN" else ", "
        labels = separator.join(value["label"] for value in improvements)
        focus_text = text["focus"].format(labels=labels)
    else:
        focus_text = text["no_focus"]
    quality_notice = text["quality"] if _quality_needs_caution(report) else None
    spoken_parts = [score_text, headline + ("。" if locale == "zh-CN" else "."), focus_text]
    if quality_notice:
        spoken_parts.append(quality_notice)

    return {
        "format": SUMMARY_FORMAT,
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "created_at": _created_at(),
        "locale": locale,
        "overall_score": rounded_score,
        "rating": {"id": rating_id, "headline": headline},
        "improvements": improvements,
        "quality_notice": quality_notice,
        "spoken_text": " ".join(spoken_parts),
        "disclaimer": text["disclaimer"],
    }
