def attendance_summary(subject):
    total = subject.total_classes
    attended = subject.classes_attended
    missed = total - attended
    percentage = round(attended * 100 / total, 1) if total else 0.0
    target = subject.minimum_attendance_percentage
    if total and percentage >= target:
        needed = 0
    elif target >= 100:
        needed = None
    else:
        import math
        needed = max(0, math.ceil(((target / 100) * total - attended) / (1 - target / 100)))
    return {
        "total": total, "attended": attended, "missed": missed,
        "percentage": percentage, "target": target, "classes_to_target": needed
    }
