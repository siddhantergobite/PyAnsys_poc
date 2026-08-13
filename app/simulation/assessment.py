"""Screening-level failure assessment shared by every PoC template.

The solver is intentionally linear-elastic. This module therefore reports a
reference-strength screening result and large-deformation warning; it does not
claim to predict an exact fracture load.
"""

from __future__ import annotations

from dataclasses import dataclass
from textwrap import shorten, wrap
from typing import Any

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


DEFORMATION_LIMIT_RATIO = 0.10


@dataclass(frozen=True)
class FailureAssessment:
    """Result fields for the dynamic failure-screening layer."""

    failure_status: str
    breakage_assessment: str
    failure_criterion: str
    stress_utilization: float | None
    deformation_ratio: float | None
    large_deformation_warning: bool
    deformation_reference_length_m: float | None
    deformation_limit_ratio: float
    critical_stress_location: str
    critical_displacement_location: str
    load_application_location: str
    estimated_failure_load_n: float | None
    estimated_reference_strength_load_n: float | None
    estimated_deformation_limit_load_n: float | None
    governing_screening_load_n: float | None
    governing_screening_criterion: str
    failure_summary: list[str]

    def as_result_fields(self) -> dict:
        return {
            "failure_status": self.failure_status,
            "breakage_assessment": self.breakage_assessment,
            "failure_criterion": self.failure_criterion,
            "stress_utilization": self.stress_utilization,
            "deformation_ratio": self.deformation_ratio,
            "large_deformation_warning": self.large_deformation_warning,
            "deformation_reference_length_m": self.deformation_reference_length_m,
            "deformation_limit_ratio": self.deformation_limit_ratio,
            "critical_stress_location": self.critical_stress_location,
            "critical_displacement_location": self.critical_displacement_location,
            "load_application_location": self.load_application_location,
            "estimated_failure_load_n": self.estimated_failure_load_n,
            "estimated_reference_strength_load_n": self.estimated_reference_strength_load_n,
            "estimated_deformation_limit_load_n": self.estimated_deformation_limit_load_n,
            "governing_screening_load_n": self.governing_screening_load_n,
            "governing_screening_criterion": self.governing_screening_criterion,
            "failure_summary": self.failure_summary,
        }


def _force(value: float | None, unit: str = "N") -> str:
    if value is None:
        return "not available"
    if abs(value) >= 1000:
        return f"{value:,.0f} {unit}"
    if 0 < abs(value) < 0.01:
        return f"{value:.4g} {unit}"
    return f"{value:.3f} {unit}"


def _length(value: float | None) -> str:
    if value is None:
        return "not available"
    if abs(value) >= 1:
        return f"{value:.4g} m"
    return f"{value * 1000:.4g} mm"


def assess_failure(
    *,
    force_n: float,
    maximum_stress_pa: float,
    reference_strength_pa: float | None,
    maximum_displacement_m: float,
    deformation_reference_length_m: float,
    critical_stress_location: str,
    critical_displacement_location: str,
    load_application_location: str,
    load_unit: str = "N",
) -> FailureAssessment:
    """Classify the current result using transparent screening criteria.

    ``reference_strength_pa`` is the selected material card's yield/proof
    reference. A stress utilization of 1.0 means that reference has been
    reached. A deformation ratio above 10% means the small-deflection,
    linear-elastic result should not be treated as quantitatively reliable.
    Neither criterion is an exact fracture law.
    """

    utilization = None
    estimated_failure_load_n = None
    if reference_strength_pa and reference_strength_pa > 0 and maximum_stress_pa > 0:
        utilization = maximum_stress_pa / reference_strength_pa
        estimated_failure_load_n = force_n / utilization if utilization > 0 else None

    deformation_ratio = None
    if deformation_reference_length_m > 0:
        deformation_ratio = maximum_displacement_m / deformation_reference_length_m

    deformation_limit_load_n = None
    if force_n > 0 and deformation_ratio and deformation_ratio > 0:
        deformation_limit_load_n = (
            force_n * DEFORMATION_LIMIT_RATIO / deformation_ratio
        )
    strength_reached = utilization is not None and utilization >= 1.0
    large_deformation = (
        deformation_ratio is not None
        and deformation_ratio > DEFORMATION_LIMIT_RATIO
    )

    screening_candidates = []
    if estimated_failure_load_n is not None:
        screening_candidates.append(
            (estimated_failure_load_n, "reference strength")
        )
    if deformation_limit_load_n is not None:
        screening_candidates.append(
            (deformation_limit_load_n, "10% deformation validity limit")
        )
    if strength_reached and estimated_failure_load_n is not None:
        # Once the reference strength is reached, report that material
        # threshold as the governing failure screen. The deformation limit is
        # retained separately because it warns that the linear result is no
        # longer quantitatively trustworthy; it is not a fracture law.
        governing_screening_load_n = estimated_failure_load_n
        governing_screening_criterion = "reference strength"
    elif screening_candidates:
        governing_screening_load_n, governing_screening_criterion = min(
            screening_candidates, key=lambda item: item[0]
        )
    else:
        governing_screening_load_n = None
        governing_screening_criterion = "not available"

    location_line = (
        f"Critical stress: {critical_stress_location}; critical displacement: "
        f"{critical_displacement_location}."
    )

    if strength_reached:
        failure_status = "likely_failure_or_yielding"
        breakage_assessment = "likely_before_or_at_applied_load"
        summary = [
            f"Likely yielding/failure under the reference-strength criterion: stress utilization is {utilization:.2f}x.",
            (
                f"{location_line} Predicted deformation is {deformation_ratio:.2f}x the reference dimension; "
                if large_deformation
                else f"{location_line} "
            )
            + f"reference-strength load is about {_force(estimated_failure_load_n, load_unit)}; "
            + (
                f"10% deformation-validity load is about {_force(deformation_limit_load_n, load_unit)}; "
                if large_deformation
                else ""
            )
            + f"governing material screen is about {_force(governing_screening_load_n, load_unit)}.",
            "Exact fracture cannot be determined from this linear-elastic PoC; nonlinear material and failure data are required.",
        ]
    elif large_deformation:
        failure_status = "large_deformation_warning"
        breakage_assessment = "not_determinable_due_to_large_deformation"
        summary = [
            f"Stress is below the reference strength, but deformation is {deformation_ratio:.2f}x the reference dimension.",
            f"{location_line} The 10% deformation-validity load is about {_force(deformation_limit_load_n, load_unit)}; reference-strength load is about {_force(estimated_failure_load_n, load_unit)}.",
            "This indicates severe deformation/serviceability risk, not proof of physical fracture.",
        ]
    elif utilization is not None:
        failure_status = "within_reference_strength"
        breakage_assessment = "not_indicated_at_applied_load"
        summary = [
            f"No reference-strength exceedance at this load; stress utilization is {utilization:.2f}x.",
            f"{location_line} Estimated reference-strength load is about {_force(estimated_failure_load_n, load_unit)}; governing screening load is about {_force(governing_screening_load_n, load_unit)}.",
            "This is an elastic screening result and does not certify real-world fracture safety.",
        ]
    else:
        failure_status = "not_evaluated"
        breakage_assessment = "not_determinable"
        summary = [
            "A reference-strength failure screen could not be evaluated for this result.",
            "Check that the material card and solver stress result are valid.",
            "Exact fracture cannot be determined without a validated nonlinear failure model.",
        ]

    return FailureAssessment(
        failure_status=failure_status,
        breakage_assessment=breakage_assessment,
        failure_criterion="reference_strength_and_large_deformation_screening",
        stress_utilization=utilization,
        deformation_ratio=deformation_ratio,
        large_deformation_warning=large_deformation,
        deformation_reference_length_m=deformation_reference_length_m,
        deformation_limit_ratio=DEFORMATION_LIMIT_RATIO,
        critical_stress_location=critical_stress_location,
        critical_displacement_location=critical_displacement_location,
        load_application_location=load_application_location,
        estimated_failure_load_n=estimated_failure_load_n,
        estimated_reference_strength_load_n=estimated_failure_load_n,
        estimated_deformation_limit_load_n=deformation_limit_load_n,
        governing_screening_load_n=governing_screening_load_n,
        governing_screening_criterion=governing_screening_criterion,
        failure_summary=summary,
    )


STATUS_COLOURS = {
    "likely_failure_or_yielding": "#a3281c",
    "large_deformation_warning": "#a05a00",
    "within_reference_strength": "#087443",
    "not_evaluated": "#52677d",
}


def status_text(status: str) -> tuple[str, str]:
    labels = {
        "likely_failure_or_yielding": ("LIKELY YIELDING / FAILURE", "#a3281c"),
        "large_deformation_warning": ("LARGE-DEFORMATION WARNING", "#a05a00"),
        "within_reference_strength": ("WITHIN REFERENCE STRENGTH", "#087443"),
        "not_evaluated": ("NOT EVALUATED", "#52677d"),
    }
    return labels.get(status, (status.upper(), "#52677d"))


def add_assessment_footer(
    figure,
    *,
    force_n: float,
    reference_strength_pa: float | None,
    assessment: FailureAssessment,
    break_force_n: float | None = None,
) -> None:
    """Add the shared dynamic screen to the bottom of an existing plot."""

    status_label, status_colour = status_text(assessment.failure_status)
    threshold = (
        break_force_n
        if break_force_n is not None
        else assessment.estimated_reference_strength_load_n
    )
    utilisation = (
        f"{assessment.stress_utilization:.2f}x"
        if assessment.stress_utilization is not None
        else "not available"
    )
    reference_label = (
        f"reference strength {reference_strength_pa / 1e6:.3g} MPa"
        if reference_strength_pa is not None
        else "reference strength unavailable"
    )
    threshold_label = (
        f"threshold {_force(threshold)}"
        if threshold is not None
        else "threshold unavailable"
    )
    critical = shorten(
        f"Critical stress: {assessment.critical_stress_location}; "
        f"critical displacement: {assessment.critical_displacement_location}.",
        width=190,
        placeholder="...",
    )
    summary = shorten(
        assessment.failure_summary[0] if assessment.failure_summary else "Assessment unavailable.",
        width=190,
        placeholder="...",
    )
    figure.patches.append(
        FancyBboxPatch(
            (0.02, 0.025),
            0.96,
            0.17,
            transform=figure.transFigure,
            boxstyle="round,pad=0.006,rounding_size=0.008",
            facecolor="#f7fbfb" if assessment.failure_status == "within_reference_strength" else "#fff7f5",
            edgecolor=status_colour,
            linewidth=1.3,
            zorder=5,
        )
    )
    figure.text(
        0.04,
        0.158,
        status_label,
        color=status_colour,
        fontsize=9.2,
        fontweight="bold",
        va="center",
        zorder=6,
    )
    figure.text(
        0.31,
        0.158,
        f"Applied {_force(force_n)} | {reference_label} | {threshold_label} | utilization {utilisation}",
        color="#31506a",
        fontsize=8.2,
        va="center",
        zorder=6,
    )
    figure.text(0.04, 0.115, critical, color="#31506a", fontsize=7.8, zorder=6)
    figure.text(0.04, 0.078, summary, color="#31506a", fontsize=7.8, zorder=6)
    figure.text(
        0.04,
        0.043,
        "Screening only: this is not an exact physical fracture prediction.",
        color="#8a9aaa",
        fontsize=7.4,
        zorder=6,
    )


def add_force_response_inset(
    figure,
    *,
    position: list[float],
    force_curve: list[dict[str, Any]] | None,
    reference_strength_pa: float | None,
    break_force_n: float | None,
    deformation_reference_length_m: float | None,
    response: str,
) -> None:
    """Add a compact force-response inset to an existing result image."""

    if not force_curve or len(force_curve) < 2:
        return
    forces = np.asarray([float(point["force_n"]) for point in force_curve])
    statuses = [str(point.get("failure_status", "not_evaluated")) for point in force_curve]
    if response == "stress":
        values = np.asarray([float(point["maximum_stress_pa"]) / 1e6 for point in force_curve])
        ylabel = "Max stress (MPa)"
        title = "Force sweep - stress"
        reference = reference_strength_pa / 1e6 if reference_strength_pa else None
    else:
        values = np.asarray([float(point["maximum_displacement_m"]) * 1e3 for point in force_curve])
        ylabel = "Max displacement (mm)"
        title = "Force sweep - displacement"
        reference = (
            deformation_reference_length_m * DEFORMATION_LIMIT_RATIO * 1e3
            if deformation_reference_length_m
            else None
        )

    axis = figure.add_axes(position, facecolor="white", zorder=4)
    axis.plot(forces, values, color="#315f89", linewidth=1.5, zorder=1)
    point_colours = [STATUS_COLOURS.get(status, "#52677d") for status in statuses]
    axis.scatter(forces, values, c=point_colours, s=22, edgecolors="white", linewidths=0.5, zorder=2)
    if reference is not None:
        label = "Strength" if response == "stress" else "10% validity"
        axis.axhline(reference, color="#cc4b37", linestyle="--", linewidth=1.0, label=label)
    if break_force_n is not None and forces.min() <= break_force_n <= forces.max():
        axis.axvline(break_force_n, color="#cc4b37", linestyle=":", linewidth=1.2)
        axis.text(
            break_force_n,
            0.96,
            f"{_force(break_force_n)}",
            transform=axis.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=6.5,
            color="#9a321f",
            fontweight="bold",
        )
    axis.set_title(title, fontsize=8.5, fontweight="bold", pad=4)
    axis.set_xlabel("Force (N)", fontsize=7)
    axis.set_ylabel(ylabel, fontsize=7)
    axis.tick_params(labelsize=6.5)
    axis.grid(alpha=0.22)
    if reference is not None:
        axis.legend(fontsize=6.2, loc="upper left", frameon=True)


def export_failure_assessment_image(
    output_dir,
    *,
    template: str,
    material: str,
    force_n: float,
    maximum_stress_pa: float,
    maximum_displacement_m: float,
    reference_strength_pa: float | None,
    assessment: FailureAssessment,
    break_force_n: float | None = None,
    load_unit: str = "N",
) -> str:
    """Export a standalone, readable failure-screening report image."""

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "failure_assessment.png"
    status_label, status_colour = status_text(assessment.failure_status)
    threshold = break_force_n if break_force_n is not None else assessment.governing_screening_load_n
    reference_label = (
        f"{reference_strength_pa / 1e6:.3g} MPa" if reference_strength_pa is not None else "not available"
    )
    utilisation = (
        f"{assessment.stress_utilization:.3f}x" if assessment.stress_utilization is not None else "not available"
    )
    deformation = (
        f"{assessment.deformation_ratio:.3f}x" if assessment.deformation_ratio is not None else "not available"
    )

    figure = plt.figure(figsize=(11, 7.1), facecolor="#f7fbfb")
    figure.text(0.06, 0.92, "DYNAMIC FAILURE SCREENING", color="#087f78", fontsize=10, fontweight="bold")
    figure.text(0.06, 0.86, f"{template} - {material}", color="#17334f", fontsize=20, fontweight="bold")
    figure.text(0.06, 0.77, status_label, color=status_colour, fontsize=16, fontweight="bold")

    left_metrics = [
        ("Applied load", _force(force_n, load_unit)),
        ("Maximum stress", f"{maximum_stress_pa / 1e6:.3f} MPa"),
        ("Reference strength", reference_label),
        ("Stress utilization", utilisation),
        ("Maximum displacement", _length(maximum_displacement_m)),
        ("Deformation ratio", deformation),
        ("Estimated threshold", _force(threshold, load_unit)),
    ]
    for index, (label, value) in enumerate(left_metrics):
        y = 0.67 - index * 0.055
        figure.text(0.08, y, label, color="#7a91a8", fontsize=9)
        figure.text(0.31, y, value, color="#17334f", fontsize=10, fontweight="bold")

    figure.text(0.57, 0.67, "Critical stress location", color="#7a91a8", fontsize=9)
    figure.text(0.57, 0.62, "\n".join(wrap(assessment.critical_stress_location, width=40)), color="#17334f", fontsize=10, fontweight="bold")
    figure.text(0.57, 0.49, "Critical displacement location", color="#7a91a8", fontsize=9)
    figure.text(0.57, 0.44, "\n".join(wrap(assessment.critical_displacement_location, width=40)), color="#17334f", fontsize=10, fontweight="bold")
    figure.text(0.57, 0.31, "Load application", color="#7a91a8", fontsize=9)
    figure.text(0.57, 0.26, "\n".join(wrap(assessment.load_application_location, width=40)), color="#17334f", fontsize=10, fontweight="bold")

    figure.text(0.06, 0.17, "RESULT SUMMARY", color="#087f78", fontsize=10, fontweight="bold")
    summary_lines = []
    for item in assessment.failure_summary[:3]:
        summary_lines.extend(f"- {line}" for line in wrap(item, width=125))
    figure.text(0.06, 0.135, "\n".join(summary_lines), color="#31506a", fontsize=8.8, va="top")
    figure.text(0.06, 0.035, "Screening only: reference-strength crossing is not an exact physical fracture prediction.", color="#8a9aaa", fontsize=8.5)
    figure.savefig(path, dpi=180, bbox_inches="tight", facecolor=figure.get_facecolor())
    plt.close(figure)
    return path.name


def export_force_sweep_image(
    output_dir,
    *,
    curve: list[dict[str, Any]],
    reference_strength_pa: float,
    strength_basis: str,
    break_force_n: float | None,
    load_label: str = "force",
    load_unit: str = "N",
) -> str:
    """Export a readable two-panel force-response report."""

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "force_sweep.png"
    forces = np.asarray([float(point["force_n"]) for point in curve])
    stress_mpa = np.asarray([float(point["maximum_stress_pa"]) / 1e6 for point in curve])
    displacement_mm = np.asarray(
        [float(point["maximum_displacement_m"]) * 1e3 for point in curve]
    )
    reference_mpa = reference_strength_pa / 1e6

    figure, (stress_axis, displacement_axis) = plt.subplots(1, 2, figsize=(12, 5.2))
    statuses = [str(point.get("failure_status", "not_evaluated")) for point in curve]
    point_colours = [STATUS_COLOURS.get(status, "#52677d") for status in statuses]
    stress_axis.plot(forces, stress_mpa, color="#0a8f83", linewidth=2.4, zorder=1)
    stress_axis.scatter(forces, stress_mpa, c=point_colours, s=46, edgecolors="white", linewidths=0.6, zorder=2)
    reference_in_response = (
        float(stress_mpa.min()) <= reference_mpa <= float(stress_mpa.max())
    )
    if reference_in_response:
        stress_axis.axhline(
            reference_mpa,
            color="#cc4b37",
            linestyle="--",
            linewidth=1.5,
            label=f"Reference {strength_basis}: {reference_mpa:.1f} MPa",
        )
        stress_axis.fill_between(forces, stress_mpa, reference_mpa, where=stress_mpa <= reference_mpa, color="#d9f1e9", alpha=0.8)
        stress_axis.fill_between(forces, stress_mpa, reference_mpa, where=stress_mpa > reference_mpa, color="#fde0d7", alpha=0.9)
    else:
        stress_axis.fill_between(
            forces,
            0.0,
            stress_mpa,
            color="#d9f1e9" if reference_mpa > float(stress_mpa.max()) else "#fde0d7",
            alpha=0.65,
        )
    threshold_in_range = (
        break_force_n is not None
        and float(forces.min()) <= break_force_n <= float(forces.max())
    )
    if threshold_in_range:
        stress_axis.axvline(break_force_n, color="#cc4b37", linestyle=":", linewidth=2)
        stress_axis.annotate(
            f"Threshold about {break_force_n:.0f} {load_unit}",
            xy=(break_force_n, reference_mpa),
            xytext=(7, 10),
            textcoords="offset points",
            color="#9a321f",
            fontweight="bold",
        )
    elif break_force_n is not None:
        range_side = "below range" if break_force_n < float(forces.min()) else "above range"
        stress_axis.text(
            0.98,
            0.88,
            f"Reference: {reference_mpa:.1f} MPa\nEstimated threshold: {break_force_n:.0f} {load_unit} ({range_side})",
            transform=stress_axis.transAxes,
            ha="right",
            va="top",
            color="#9a321f",
            fontweight="bold",
            fontsize=9,
        )
    stress_axis.set_title("Maximum stress", fontweight="bold")
    stress_axis.set_xlabel(f"Applied {load_label} ({load_unit})")
    stress_axis.set_ylabel("Maximum stress (MPa)")
    stress_axis.grid(alpha=0.25)
    if reference_in_response:
        stress_axis.legend(fontsize=8, loc="upper left")

    displacement_axis.plot(forces, displacement_mm, color="#315f89", linewidth=2.2)
    displacement_axis.scatter(forces, displacement_mm, c=point_colours, s=46, edgecolors="white", linewidths=0.6, zorder=2)
    if threshold_in_range:
        displacement_axis.axvline(break_force_n, color="#cc4b37", linestyle=":", linewidth=2)
    displacement_axis.set_title("Maximum displacement", fontweight="bold")
    displacement_axis.set_xlabel(f"Applied {load_label} ({load_unit})")
    displacement_axis.set_ylabel("Maximum displacement (mm)")
    displacement_axis.grid(alpha=0.25)
    figure.suptitle(f"MAPDL {load_label} sweep", fontsize=15, fontweight="bold")
    figure.text(
        0.5,
        0.015,
        "Reference-strength crossing is an elastic screening threshold, not a physical break prediction.",
        ha="center",
        fontsize=9,
        color="#52677d",
    )
    figure.tight_layout(rect=(0, 0.06, 1, 0.93))
    figure.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    return path.name
