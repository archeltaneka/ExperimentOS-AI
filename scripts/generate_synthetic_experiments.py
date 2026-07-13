from __future__ import annotations

# ruff: noqa: E501
import csv
import json
import random
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = ROOT / "data" / "synthetic" / "experiments"
COUNTRIES = ["US", "GB", "AU", "DE", "FR", "JP", "SG", "BR", "IN", "CA"]
PLATFORMS = ["ios", "android", "web", "mobile_web"]
SEGMENTS = ["new", "returning", "loyalty_silver", "loyalty_gold", "high_intent"]


@dataclass(frozen=True)
class MetricSpec:
    name: str
    unit: str
    control: float
    treatment: float
    p_value: float
    numerator_rate: float | None = None
    notes: str = ""


@dataclass(frozen=True)
class ExperimentSpec:
    experiment_id: str
    name: str
    area: str
    hypothesis: str
    owner_name: str
    owner_team: str
    status: str
    business_decision: str
    primary_metric: str
    secondary_metrics: list[str]
    start_date: str
    end_date: str
    control_users: int
    treatment_users: int
    control_event_rate: float
    treatment_event_rate: float
    event_names: list[str]
    metrics: list[MetricSpec]
    imperfections: list[str]
    recommendation: str
    risk_summary: str


EXPERIMENTS = [
    ExperimentSpec(
        experiment_id="exp-001-payment-recommendation",
        name="Adaptive Payment Method Recommendation",
        area="payment recommendation",
        hypothesis=(
            "Ranking locally preferred payment methods above generic card options will reduce "
            "checkout hesitation and raise successful payment completion."
        ),
        owner_name="Maya Chen",
        owner_team="Payments Optimization",
        status="completed",
        business_decision="Roll out to AU, SG, and GB; hold JP pending wallet tracking fix.",
        primary_metric="payment_success_rate",
        secondary_metrics=["checkout_completion_rate", "payment_retry_rate", "revenue_per_user"],
        start_date="2026-01-12",
        end_date="2026-01-26",
        control_users=68,
        treatment_users=78,
        control_event_rate=0.676,
        treatment_event_rate=0.731,
        event_names=[
            "payment_method_viewed",
            "payment_selected",
            "payment_success",
            "payment_retry",
        ],
        metrics=[
            MetricSpec("payment_success_rate", "rate", 0.676, 0.731, 0.041, 0.676),
            MetricSpec("checkout_completion_rate", "rate", 0.642, 0.701, 0.052, 0.642),
            MetricSpec("payment_retry_rate", "rate", 0.118, 0.083, 0.083, 0.118),
            MetricSpec("revenue_per_user", "usd", 96.40, 101.70, 0.117),
        ],
        imperfections=[
            "Sample ratio mismatch from late allocation rule change in mobile web.",
            "Japan wallet success events were under-counted for the first 18 hours.",
            "Country-specific behaviour: local wallets performed better in AU and SG than in US.",
        ],
        recommendation="Ship to markets with clean wallet telemetry and keep JP behind monitoring.",
        risk_summary="A bad payment ranking can suppress trusted methods in smaller markets.",
    ),
    ExperimentSpec(
        experiment_id="exp-002-hotel-image-quality",
        name="Hotel Gallery Image Quality Boost",
        area="hotel image quality",
        hypothesis=(
            "Prioritizing brighter, higher-resolution lead photos will increase property detail "
            "engagement and booking intent on hotel search results."
        ),
        owner_name="Oliver Smith",
        owner_team="Lodging Merchandising",
        status="rolled_out",
        business_decision="Roll out globally except markets with pending image CDN latency regressions.",
        primary_metric="booking_intent_rate",
        secondary_metrics=["gallery_open_rate", "property_save_rate", "image_load_p95_ms"],
        start_date="2026-02-02",
        end_date="2026-02-16",
        control_users=72,
        treatment_users=72,
        control_event_rate=0.292,
        treatment_event_rate=0.347,
        event_names=["hotel_card_viewed", "gallery_opened", "property_saved", "booking_intent"],
        metrics=[
            MetricSpec("booking_intent_rate", "rate", 0.292, 0.347, 0.036, 0.292),
            MetricSpec("gallery_open_rate", "rate", 0.438, 0.514, 0.018, 0.438),
            MetricSpec("property_save_rate", "rate", 0.181, 0.206, 0.214, 0.181),
            MetricSpec("image_load_p95_ms", "ms", 1180, 1345, 0.064),
        ],
        imperfections=[
            "Seasonality from a school-holiday travel spike in AU increased beach hotel traffic.",
            "CDN cache warm-up caused higher image latency during the first two days.",
        ],
        recommendation="Roll out while enforcing image byte-size budgets and CDN pre-warming.",
        risk_summary="Higher quality imagery can slow weaker devices and harm low-bandwidth users.",
    ),
    ExperimentSpec(
        experiment_id="exp-003-search-ranking",
        name="Intent-Aware Search Ranking",
        area="search ranking",
        hypothesis=(
            "Blending query intent with historical conversion quality will lift result clicks and "
            "orders without reducing result diversity."
        ),
        owner_name="Aisha Rahman",
        owner_team="Search Relevance",
        status="monitoring",
        business_decision="Continue monitoring for long-tail query diversity before broader rollout.",
        primary_metric="search_to_order_rate",
        secondary_metrics=["result_click_rate", "zero_result_rate", "diversity_score"],
        start_date="2026-02-20",
        end_date="2026-03-06",
        control_users=80,
        treatment_users=70,
        control_event_rate=0.183,
        treatment_event_rate=0.211,
        event_names=["search_submitted", "result_clicked", "filter_applied", "order_created"],
        metrics=[
            MetricSpec("search_to_order_rate", "rate", 0.183, 0.211, 0.091, 0.183),
            MetricSpec("result_click_rate", "rate", 0.392, 0.431, 0.072, 0.392),
            MetricSpec("zero_result_rate", "rate", 0.047, 0.043, 0.402, 0.047),
            MetricSpec("diversity_score", "score", 0.812, 0.776, 0.049),
        ],
        imperfections=[
            "Sample ratio mismatch caused by search cache bucketing on anonymous sessions.",
            "Treatment reduced supplier diversity for long-tail searches in Germany.",
        ],
        recommendation="Tune diversity guardrail before ramping beyond 25 percent of traffic.",
        risk_summary="Ranking improvements can concentrate exposure among already popular suppliers.",
    ),
    ExperimentSpec(
        experiment_id="exp-004-checkout-ux",
        name="One-Page Checkout UX",
        area="checkout ux",
        hypothesis=(
            "Combining shipping, payment, and review into a single checkout step will reduce "
            "drop-off for returning customers."
        ),
        owner_name="Diego Martinez",
        owner_team="Checkout Experience",
        status="completed",
        business_decision="Roll out to returning users; keep first-time users on guided checkout.",
        primary_metric="checkout_completion_rate",
        secondary_metrics=["form_error_rate", "support_contact_rate", "average_order_value"],
        start_date="2026-03-10",
        end_date="2026-03-24",
        control_users=75,
        treatment_users=75,
        control_event_rate=0.584,
        treatment_event_rate=0.638,
        event_names=[
            "checkout_started",
            "address_completed",
            "payment_submitted",
            "order_completed",
        ],
        metrics=[
            MetricSpec("checkout_completion_rate", "rate", 0.584, 0.638, 0.044, 0.584),
            MetricSpec("form_error_rate", "rate", 0.164, 0.191, 0.126, 0.164),
            MetricSpec("support_contact_rate", "rate", 0.031, 0.038, 0.317, 0.031),
            MetricSpec("average_order_value", "usd", 74.20, 76.10, 0.281),
        ],
        imperfections=[
            "Novelty effects: repeat visitors completed faster during week one than week two.",
            "Address autocomplete telemetry missed apartment-unit edits on mobile Safari.",
        ],
        recommendation="Launch for returning users and run a separate first-time buyer study.",
        risk_summary="Compressed checkout can hide errors until final submission.",
    ),
    ExperimentSpec(
        experiment_id="exp-005-pricing",
        name="Transparent Discount Price Framing",
        area="pricing",
        hypothesis=(
            "Showing the final discounted price earlier will improve conversion while preserving "
            "gross margin and reducing promo-code hunting."
        ),
        owner_name="Priya Nair",
        owner_team="Pricing Strategy",
        status="stopped",
        business_decision="Do not roll out; conversion gain did not offset margin dilution.",
        primary_metric="gross_margin_per_visitor",
        secondary_metrics=["purchase_conversion_rate", "promo_code_attempt_rate", "refund_rate"],
        start_date="2026-03-28",
        end_date="2026-04-08",
        control_users=76,
        treatment_users=74,
        control_event_rate=4.86,
        treatment_event_rate=4.71,
        event_names=["price_viewed", "promo_code_entered", "cart_created", "purchase_completed"],
        metrics=[
            MetricSpec("gross_margin_per_visitor", "usd", 4.86, 4.71, 0.188),
            MetricSpec("purchase_conversion_rate", "rate", 0.096, 0.108, 0.153, 0.096),
            MetricSpec("promo_code_attempt_rate", "rate", 0.204, 0.141, 0.021, 0.204),
            MetricSpec("refund_rate", "rate", 0.017, 0.019, 0.664, 0.017),
        ],
        imperfections=[
            "Seasonality from end-of-quarter promotions inflated baseline discount sensitivity.",
            "Country-specific behaviour: Germany showed margin loss despite flat conversion.",
        ],
        recommendation="Stop current variant and retest with clearer savings copy but no deeper discounts.",
        risk_summary="Price framing can train customers to wait for visible discounts.",
    ),
    ExperimentSpec(
        experiment_id="exp-006-loyalty",
        name="Loyalty Tier Progress Nudges",
        area="loyalty",
        hypothesis=(
            "Showing progress toward the next loyalty tier after purchase will increase repeat "
            "engagement and second booking intent."
        ),
        owner_name="Hannah Lee",
        owner_team="Lifecycle Loyalty",
        status="completed",
        business_decision="Roll out to silver and gold members with a frequency cap.",
        primary_metric="repeat_session_rate_14d",
        secondary_metrics=[
            "tier_progress_click_rate",
            "unsubscribe_rate",
            "points_redemption_rate",
        ],
        start_date="2026-04-12",
        end_date="2026-04-26",
        control_users=70,
        treatment_users=82,
        control_event_rate=0.274,
        treatment_event_rate=0.329,
        event_names=[
            "post_purchase_viewed",
            "tier_progress_opened",
            "reward_clicked",
            "repeat_session",
        ],
        metrics=[
            MetricSpec("repeat_session_rate_14d", "rate", 0.274, 0.329, 0.027, 0.274),
            MetricSpec("tier_progress_click_rate", "rate", 0.119, 0.238, 0.004, 0.119),
            MetricSpec("unsubscribe_rate", "rate", 0.006, 0.011, 0.241, 0.006),
            MetricSpec("points_redemption_rate", "rate", 0.064, 0.079, 0.182, 0.064),
        ],
        imperfections=[
            "Sample ratio mismatch from delayed exclusion of dormant loyalty accounts.",
            "Novelty effect in the first three days increased progress-panel clicks.",
        ],
        recommendation="Ship with notification caps and monitor unsubscribe rates weekly.",
        risk_summary="Too many loyalty prompts can make transactional surfaces feel promotional.",
    ),
    ExperimentSpec(
        experiment_id="exp-007-crm-notifications",
        name="CRM Back-in-Stock Notification Timing",
        area="crm notifications",
        hypothesis=(
            "Sending back-in-stock alerts within ten minutes of inventory recovery will increase "
            "reactivation without materially increasing opt-outs."
        ),
        owner_name="Marcus Johnson",
        owner_team="CRM Growth",
        status="completed",
        business_decision="Roll out for opted-in customers outside quiet hours.",
        primary_metric="reactivation_purchase_rate",
        secondary_metrics=["notification_open_rate", "unsubscribe_rate", "complaint_rate"],
        start_date="2026-05-01",
        end_date="2026-05-15",
        control_users=73,
        treatment_users=77,
        control_event_rate=0.073,
        treatment_event_rate=0.091,
        event_names=[
            "notification_sent",
            "notification_opened",
            "product_viewed",
            "purchase_completed",
        ],
        metrics=[
            MetricSpec("reactivation_purchase_rate", "rate", 0.073, 0.091, 0.048, 0.073),
            MetricSpec("notification_open_rate", "rate", 0.284, 0.337, 0.031, 0.284),
            MetricSpec("unsubscribe_rate", "rate", 0.013, 0.017, 0.311, 0.013),
            MetricSpec("complaint_rate", "rate", 0.002, 0.003, 0.572, 0.002),
        ],
        imperfections=[
            "Tracking issue: Android push opens were duplicated for six hours after SDK rollout.",
            "Country-specific quiet-hour rules changed treatment exposure in Japan and Germany.",
        ],
        recommendation="Launch with deduplicated Android events and country-specific quiet-hour rules.",
        risk_summary="Faster CRM messages may be perceived as intrusive if inventory changes repeatedly.",
    ),
    ExperimentSpec(
        experiment_id="exp-008-recommendation-systems",
        name="Personalized Similar-Item Recommendations",
        area="recommendation systems",
        hypothesis=(
            "Adding session-aware similar-item recommendations to product pages will increase "
            "add-to-cart rate while keeping discovery broad."
        ),
        owner_name="Sofia Rossi",
        owner_team="Recommendations",
        status="monitoring",
        business_decision="Hold at 15 percent traffic while monitoring category concentration.",
        primary_metric="add_to_cart_rate",
        secondary_metrics=[
            "recommendation_click_rate",
            "category_diversity_score",
            "revenue_per_user",
        ],
        start_date="2026-05-18",
        end_date="2026-06-01",
        control_users=79,
        treatment_users=79,
        control_event_rate=0.214,
        treatment_event_rate=0.246,
        event_names=[
            "product_viewed",
            "recommendation_seen",
            "recommendation_clicked",
            "cart_added",
        ],
        metrics=[
            MetricSpec("add_to_cart_rate", "rate", 0.214, 0.246, 0.061, 0.214),
            MetricSpec("recommendation_click_rate", "rate", 0.086, 0.127, 0.016, 0.086),
            MetricSpec("category_diversity_score", "score", 0.744, 0.706, 0.043),
            MetricSpec("revenue_per_user", "usd", 8.60, 9.35, 0.109),
        ],
        imperfections=[
            "Novelty effect from a new carousel placement increased clicks in week one.",
            "Treatment over-recommended premium accessories for US desktop users.",
        ],
        recommendation="Tune category diversity constraints before expanding traffic.",
        risk_summary="Personalization can narrow discovery and overfit to recent browsing.",
    ),
    ExperimentSpec(
        experiment_id="exp-009-search-filters",
        name="Dynamic Search Filter Shortcuts",
        area="search filters",
        hypothesis=(
            "Surfacing query-specific filter shortcuts will help users narrow results faster and "
            "increase qualified result clicks."
        ),
        owner_name="Noah Brown",
        owner_team="Search Experience",
        status="completed",
        business_decision="Roll out to high-volume categories after fixing mobile web scroll tracking.",
        primary_metric="qualified_result_click_rate",
        secondary_metrics=["filter_apply_rate", "time_to_first_click_seconds", "zero_result_rate"],
        start_date="2026-06-03",
        end_date="2026-06-17",
        control_users=71,
        treatment_users=85,
        control_event_rate=0.316,
        treatment_event_rate=0.369,
        event_names=[
            "search_submitted",
            "shortcut_filter_seen",
            "filter_applied",
            "result_clicked",
        ],
        metrics=[
            MetricSpec("qualified_result_click_rate", "rate", 0.316, 0.369, 0.019, 0.316),
            MetricSpec("filter_apply_rate", "rate", 0.228, 0.342, 0.006, 0.228),
            MetricSpec("time_to_first_click_seconds", "seconds", 38.4, 31.2, 0.033),
            MetricSpec("zero_result_rate", "rate", 0.052, 0.058, 0.286, 0.052),
        ],
        imperfections=[
            "Sample ratio mismatch caused by category pages entering the experiment late.",
            "Mobile web scroll tracking dropped some shortcut impressions.",
        ],
        recommendation="Ship to high-volume categories with corrected impression tracking.",
        risk_summary="Aggressive shortcuts can over-filter results and raise zero-result rates.",
    ),
    ExperimentSpec(
        experiment_id="exp-010-premium-subscriptions",
        name="Premium Subscription Trial Offer",
        area="premium subscriptions",
        hypothesis=(
            "A contextual seven-day premium trial offer after the third booking search will raise "
            "subscription starts without cannibalizing paid annual plans."
        ),
        owner_name="Emma Wilson",
        owner_team="Subscriptions",
        status="completed",
        business_decision="Roll out to eligible non-subscribers with annual-plan exclusion logic.",
        primary_metric="trial_start_rate",
        secondary_metrics=[
            "paid_conversion_rate_30d",
            "annual_plan_purchase_rate",
            "support_ticket_rate",
        ],
        start_date="2026-06-18",
        end_date="2026-07-02",
        control_users=77,
        treatment_users=73,
        control_event_rate=0.041,
        treatment_event_rate=0.068,
        event_names=["premium_offer_seen", "benefit_expanded", "trial_started", "plan_purchased"],
        metrics=[
            MetricSpec("trial_start_rate", "rate", 0.041, 0.068, 0.022, 0.041),
            MetricSpec("paid_conversion_rate_30d", "rate", 0.018, 0.023, 0.196, 0.018),
            MetricSpec("annual_plan_purchase_rate", "rate", 0.011, 0.008, 0.288, 0.011),
            MetricSpec("support_ticket_rate", "rate", 0.004, 0.007, 0.377, 0.004),
        ],
        imperfections=[
            "Seasonality: July holiday planning lifted premium benefit interest in AU and US.",
            "Trial-start tracking lagged by one day for Apple in-app subscriptions.",
        ],
        recommendation="Roll out with annual-plan cannibalization guardrails and billing telemetry checks.",
        risk_summary="Trial offers can defer annual purchases and create billing-support contacts.",
    ),
]


def count_for_rate(total: int, rate: float) -> int:
    return max(0, min(total, round(total * rate)))


def write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def metric_rows(spec: ExperimentSpec) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    sample_sizes = {"control": spec.control_users, "treatment": spec.treatment_users}
    for variant, sample_size in sample_sizes.items():
        rows.append(
            {
                "experiment_id": spec.experiment_id,
                "metric_name": "sample_size",
                "variant": variant,
                "value": sample_size,
                "unit": "users",
                "numerator": sample_size,
                "denominator": sample_size,
                "lift_vs_control": "0.0000" if variant == "control" else "",
                "p_value": "",
                "notes": "User-level assignment count used for sample-ratio checks.",
            }
        )

    control_values = {metric.name: metric.control for metric in spec.metrics}
    for metric in spec.metrics:
        for variant, value in [("control", metric.control), ("treatment", metric.treatment)]:
            denominator = sample_sizes[variant] if metric.unit == "rate" else ""
            numerator = (
                count_for_rate(sample_sizes[variant], value) if metric.unit == "rate" else ""
            )
            lift = (
                0.0
                if variant == "control"
                else (value - control_values[metric.name]) / control_values[metric.name]
            )
            rows.append(
                {
                    "experiment_id": spec.experiment_id,
                    "metric_name": metric.name,
                    "variant": variant,
                    "value": f"{value:.4f}" if metric.unit == "rate" else f"{value:.2f}",
                    "unit": metric.unit,
                    "numerator": numerator,
                    "denominator": denominator,
                    "lift_vs_control": f"{lift:.4f}",
                    "p_value": "" if variant == "control" else f"{metric.p_value:.3f}",
                    "notes": metric.notes
                    or (
                        "Primary decision metric."
                        if metric.name == spec.primary_metric
                        else "Secondary diagnostic metric."
                    ),
                }
            )
    return rows


def event_rows(spec: ExperimentSpec) -> list[dict[str, object]]:
    rng = random.Random(spec.experiment_id)
    start = datetime.fromisoformat(spec.start_date).replace(tzinfo=UTC)
    end = datetime.fromisoformat(spec.end_date).replace(tzinfo=UTC)
    duration_seconds = int((end - start).total_seconds())
    rows: list[dict[str, object]] = []

    for variant, total, rate in [
        ("control", spec.control_users, spec.control_event_rate),
        ("treatment", spec.treatment_users, spec.treatment_event_rate),
    ]:
        success_count = count_for_rate(total, rate) if rate <= 1 else 0
        success_indexes = set(rng.sample(range(total), success_count)) if success_count else set()
        for index in range(total):
            timestamp = start + timedelta(seconds=rng.randrange(max(1, duration_seconds)))
            country = rng.choices(
                COUNTRIES,
                weights=[22, 10, 12, 9, 8, 7, 6, 7, 11, 8],
                k=1,
            )[0]
            platform = rng.choices(PLATFORMS, weights=[31, 29, 25, 15], k=1)[0]
            segment = rng.choices(SEGMENTS, weights=[24, 34, 16, 11, 15], k=1)[0]
            converted = index in success_indexes
            event_name = spec.event_names[-1] if converted else rng.choice(spec.event_names[:-1])
            tracking_quality = "clean"
            note = ""
            if "tracking" in " ".join(spec.imperfections).lower() and rng.random() < 0.08:
                tracking_quality = "suspect"
                note = "Included in analysis with known tracking caveat."
            elif "seasonality" in " ".join(spec.imperfections).lower() and country in {"AU", "US"}:
                note = "Observed during seasonal demand window."
            elif "country-specific" in " ".join(spec.imperfections).lower() and country in {
                "DE",
                "JP",
                "AU",
                "SG",
            }:
                note = "Country behaviour called out in experiment report."

            revenue = 0.0
            if converted or "purchase" in event_name or "order" in event_name:
                revenue = round(rng.uniform(24, 260), 2)
            elif spec.area in {"pricing", "recommendation systems"}:
                revenue = round(rng.uniform(0, 14), 2)

            rows.append(
                {
                    "event_id": f"{spec.experiment_id}-evt-{variant[:1]}-{index + 1:04d}",
                    "experiment_id": spec.experiment_id,
                    "user_id": f"user-{rng.randrange(100000, 999999)}",
                    "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
                    "variant": variant,
                    "country": country,
                    "platform": platform,
                    "segment": segment,
                    "event_name": event_name,
                    "converted": str(converted).lower(),
                    "metric_value": "1" if converted else "0",
                    "revenue_usd": f"{revenue:.2f}",
                    "tracking_quality": tracking_quality,
                    "notes": note,
                }
            )
    rows.sort(key=lambda row: str(row["timestamp"]))
    return rows


def report_text(spec: ExperimentSpec) -> str:
    control_primary = next(
        metric.control for metric in spec.metrics if metric.name == spec.primary_metric
    )
    treatment_primary = next(
        metric.treatment for metric in spec.metrics if metric.name == spec.primary_metric
    )
    primary_delta = treatment_primary - control_primary
    imperfections = "; ".join(spec.imperfections)
    secondary = ", ".join(spec.secondary_metrics)

    return f"""# {spec.name}

## Background

{spec.name} was designed for the ExperimentOS synthetic corpus as a realistic example of a product experimentation decision. The product area was {spec.area}, and the team needed evidence that would be useful for a future ingestion and retrieval pipeline, not a perfect classroom test. The baseline experience already had meaningful traffic and some known operational constraints, so the experiment deliberately includes realistic noise. The owner was {spec.owner_name} from {spec.owner_team}. Traffic ran from {spec.start_date} through {spec.end_date}, long enough to observe weekday and weekend behaviour but short enough that market conditions could still influence the result. The dataset includes user-level events, aggregate metrics, metadata, and this decision report.

## Hypothesis

The hypothesis was: {spec.hypothesis} The primary metric was {spec.primary_metric}, supported by secondary metrics for {secondary}. The team expected the treatment to improve the primary metric without creating unacceptable movement in guardrail metrics. A result would be considered actionable only if the direction of movement was consistent across major user segments and if known data quality issues could be explained rather than ignored.

## Experiment Design

Users were assigned to control and treatment at the user level. Control retained the existing product experience, while treatment received the proposed change. The analysis population included {spec.control_users} control users and {spec.treatment_users} treatment users. Assignment was intended to be even, but the final counts reflect production imperfections. Events were collected across web, mobile web, iOS, and Android. The event stream records country, platform, segment, event name, conversion flag, revenue where applicable, and a tracking-quality indicator. The experiment was evaluated using an intent-to-treat approach so that users remained in their assigned variant even if they did not engage deeply with the feature.

## Results

Control recorded {control_primary:.4f} on {spec.primary_metric}, while treatment recorded {treatment_primary:.4f}. The absolute movement was {primary_delta:.4f}, and the supporting metrics were directionally consistent with the business read. The result was not interpreted mechanically from a single p-value. Instead, the team considered the size of the effect, product risk, operational cost, and segment behaviour. Metric rows in `metrics.csv` include sample size, the primary metric, and secondary diagnostics for both variants. Event rows in `events.csv` allow future retrieval tests to connect aggregate conclusions back to realistic user-level evidence.

## Limitations

This experiment has limitations that should be preserved in the synthetic data because they are common in production testing. Notable imperfections were: {imperfections}. These issues do not make the dataset unusable, but they change how confident a decision maker should be. The sample is intentionally small for repository practicality, so the reports describe realistic directional decisions rather than definitive statistical proof. Some country and platform segments are sparse, and several metrics are proxies for longer-term outcomes that would normally require follow-up measurement.

## Risks

The main risk is that the treatment effect may not generalize when exposed to broader traffic. {spec.risk_summary} There is also risk in over-reading aggregate lift when one country, platform, or segment contributes disproportionately. Tracking issues can create false confidence if they align with the treatment experience. Finally, product teams may be tempted to ship from the headline metric alone, but each report is written to require a business decision that balances upside, guardrails, and data quality.

## Recommendation

The recommendation is: {spec.recommendation} The business decision recorded in metadata is: {spec.business_decision} This recommendation reflects both the metric movement and the imperfections observed during the run. For future ExperimentOS milestones, this report should be useful as a retrieval target because it contains explicit reasoning, named metrics, known caveats, and a decision that is more nuanced than simply winning or losing.

## Future Work

Future work should include a larger follow-up test or monitored rollout, depending on the decision status. The next analysis should check whether the primary metric movement persists after novelty effects fade, whether country-specific behaviour remains stable, and whether any tracking caveats have been fixed. Future ingestion work can parse this report, link it to metadata and CSV evidence, and produce embeddings or chunks that support questions such as why the decision was made, which imperfections mattered, and what follow-up work was recommended.
"""


def metadata(spec: ExperimentSpec) -> dict[str, object]:
    return {
        "experiment_id": spec.experiment_id,
        "name": spec.name,
        "area": spec.area,
        "hypothesis": spec.hypothesis,
        "owner": {"name": spec.owner_name, "team": spec.owner_team},
        "status": spec.status,
        "start_date": spec.start_date,
        "end_date": spec.end_date,
        "variants": [
            {"name": "control", "description": "Existing production experience."},
            {"name": "treatment", "description": "Proposed product change under evaluation."},
        ],
        "primary_metric": spec.primary_metric,
        "secondary_metrics": spec.secondary_metrics,
        "imperfections": spec.imperfections,
        "business_decision": spec.business_decision,
    }


def main() -> None:
    if DATASET_ROOT.exists():
        shutil.rmtree(DATASET_ROOT)
    DATASET_ROOT.mkdir(parents=True)

    metric_fields = [
        "experiment_id",
        "metric_name",
        "variant",
        "value",
        "unit",
        "numerator",
        "denominator",
        "lift_vs_control",
        "p_value",
        "notes",
    ]
    event_fields = [
        "event_id",
        "experiment_id",
        "user_id",
        "timestamp",
        "variant",
        "country",
        "platform",
        "segment",
        "event_name",
        "converted",
        "metric_value",
        "revenue_usd",
        "tracking_quality",
        "notes",
    ]

    for spec in EXPERIMENTS:
        experiment_dir = DATASET_ROOT / spec.experiment_id
        experiment_dir.mkdir()
        write_json(experiment_dir / "metadata.json", metadata(spec))
        write_csv(experiment_dir / "metrics.csv", metric_rows(spec), metric_fields)
        write_csv(experiment_dir / "events.csv", event_rows(spec), event_fields)
        (experiment_dir / "report.md").write_text(report_text(spec), encoding="utf-8")


if __name__ == "__main__":
    main()
