#!/usr/bin/env python3
"""
生成跑步周期训练计划。
Usage:
    python3 gen_plan.py --goal half-marathon --level intermediate --weeks 12 --weekly-days 4 --target-time "01:50:00" --output runner-data.json
"""
import argparse, json, sys
from datetime import datetime, timedelta
from pathlib import Path

# 各目标的基础参数：周期建议周数、长距离上限、单周基础跑量
GOAL_CONFIG = {
    "5K":            {"default_weeks": 8,  "long_cap": 10, "base_km": 20},
    "10K":           {"default_weeks": 10, "long_cap": 18, "base_km": 30},
    "half-marathon": {"default_weeks": 12, "long_cap": 25, "base_km": 35},
    "marathon":      {"default_weeks": 16, "long_cap": 32, "base_km": 45},
    "fitness":       {"default_weeks": 8,  "long_cap": 12, "base_km": 25},
}

# 计划类型（阶段4 基于前三阶段决策）
PLAN_TYPES = {
    "couch-to-5k":     {"default_weeks": 10, "base_km": 8,  "long_cap": 6,  "walk_run": True},
    "foundation":      {"default_weeks": 8,  "base_km": 18, "long_cap": 12, "walk_run": False},
    "5k-race":         {"default_weeks": 8,  "base_km": 22, "long_cap": 10, "walk_run": False},
    "half-marathon":   {"default_weeks": 12, "base_km": 28, "long_cap": 22, "walk_run": False},
    "marathon":        {"default_weeks": 16, "base_km": 38, "long_cap": 32, "walk_run": False},
    "maintenance":     {"default_weeks": 8,  "base_km": 25, "long_cap": 14, "walk_run": False},
}

LEVEL_FACTOR = {
    "beginner":     {"vol": 0.6, "intensity": False},
    "intermediate": {"vol": 1.0, "intensity": True},
    "advanced":     {"vol": 1.3, "intensity": True},
}

# 每周训练模板：键=每周天数，值=该周的课表类型序列
WEEKLY_TEMPLATES = {
    3: ["easy", "tempo", "long"],
    4: ["easy", "interval", "tempo", "long"],
    5: ["easy", "interval", "easy", "tempo", "long"],
    6: ["easy", "interval", "easy", "tempo", "easy", "long"],
}

DAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def estimate_paces(target_time_5k=None, level="intermediate"):
    """基于 5K 目标成绩或水平推算各配速区间（分:秒/km）。"""
    # 默认参考配速（intermediate）
    if target_time_5k:
        secs = parse_time(target_time_5k)
        pace5k = secs / 5  # 秒/公里
    elif level == "beginner":
        pace5k = 6 * 60 + 30  # 6:30
    elif level == "advanced":
        pace5k = 4 * 60 + 30  # 4:30
    else:
        pace5k = 5 * 60 + 30  # 5:30

    # 各区间相对 5K 配速的偏移（秒）
    easy_low, easy_high = pace5k + 60, pace5k + 90
    tempo = pace5k + 20
    interval = pace5k - 15
    marathon = pace5k + 35
    long_low, long_high = pace5k + 70, pace5k + 110
    return {
        "easy": (easy_low, easy_high),
        "tempo": (tempo, tempo),
        "interval": (interval, interval),
        "marathon": (marathon, marathon),
        "long": (long_low, long_high),
    }


def parse_time(t):
    """HH:MM:SS 或 MM:SS → 秒。"""
    parts = t.split(":")
    parts = [int(p) for p in parts]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return parts[0] * 60 + parts[1]


def fmt_pace(secs):
    secs = int(round(secs))
    return f"{secs // 60}:{secs % 60:02d}"


def fmt_pace_range(low, high):
    return f"{fmt_pace(low)}-{fmt_pace(high)}"


def workout_detail(wtype, paces, level):
    """生成单次训练的详细内容。"""
    if wtype == "easy":
        return f"轻松跑 {fmt_pace_range(*paces['easy'])}"
    if wtype == "tempo":
        return f"热身2km + 4km@{fmt_pace(paces['tempo'][0])} + 冷身1.5km"
    if wtype == "interval":
        return "热身2km + 400m×6@" + fmt_pace(paces['interval'][0]) + " + 慢跑200m恢复 + 冷身1km"
    if wtype == "long":
        return f"长距离慢跑 {fmt_pace_range(*paces['long'])}"
    return ""


def workout_hr(wtype):
    return {"easy": "Z2", "tempo": "Z4", "interval": "Z5", "long": "Z2"}.get(wtype, "Z2")


def workout_distance(wtype, week_km, long_cap, is_deload):
    """根据周跑量分配单次距离。"""
    factor = 0.8 if is_deload else 1.0
    if wtype == "easy":
        return round(week_km * 0.22 * factor, 1)
    if wtype == "tempo":
        return round(week_km * 0.25 * factor, 1)
    if wtype == "interval":
        return round(week_km * 0.22 * factor, 1)
    if wtype == "long":
        return min(round(week_km * 0.33 * factor, 1), long_cap)
    return round(week_km * 0.2 * factor, 1)


def build_plan(goal, level, weeks, weekly_days, target_time):
    cfg = GOAL_CONFIG[goal]
    if weeks is None:
        weeks = cfg["default_weeks"]
    if weekly_days not in WEEKLY_TEMPLATES:
        raise ValueError(f"weekly_days 仅支持 3/4/5/6，收到 {weekly_days}")

    lf = LEVEL_FACTOR[level]
    base_km = cfg["base_km"] * lf["vol"]
    long_cap = cfg["long_cap"]
    paces = estimate_paces(target_time, level) if target_time else estimate_paces(None, level)

    # 若是比赛目标，根据目标完赛时间换算 5K 等效成绩
    if target_time and goal in ("half-marathon", "marathon", "10K"):
        # 粗略：全马 / 8.8 ≈ 5K 成绩（Riegel 公式反向）
        total = parse_time(target_time)
        if goal == "10K":
            equiv_5k = total / 2.08
        elif goal == "half-marathon":
            equiv_5k = total / 4.4
        else:  # marathon
            equiv_5k = total / 8.8
        paces = estimate_paces(f"{int(equiv_5k // 60):02d}:{int(equiv_5k % 60):02d}", level)

    weeks_data = []
    current_km = base_km * 0.7  # 起始略低

    for w in range(1, weeks + 1):
        progress = (w - 1) / weeks
        # 判断阶段
        if progress < 0.3:
            phase = "基础期"
            focus = "建立有氧基础"
        elif progress < 0.7:
            phase = "进展期"
            focus = "提升乳酸阈与最大摄氧量"
        elif progress < 0.9:
            phase = "巅峰期"
            focus = "专项强度与比赛配速适应"
        else:
            phase = "减量期"
            focus = "减量保强度，迎接比赛"

        # 每 4 周一次减量周，或最后 2 周
        is_deload = (w % 4 == 0) or (w >= weeks - 1)

        # 跑量递进：非减量周 +8%，减量周 -25%
        if is_deload:
            current_km = current_km * 0.75
        else:
            current_km = min(current_km * 1.08, base_km * 1.3)
        week_km = round(current_km, 1)

        template = WEEKLY_TEMPLATES[weekly_days]
        workouts = []
        for i, wtype in enumerate(template):
            dist = workout_distance(wtype, week_km, long_cap, is_deload)
            detail = workout_detail(wtype, paces, level)
            workouts.append({
                "day": DAY_NAMES[i * 2 if weekly_days <= 4 else i],  # 简化分布
                "type": wtype,
                "distance_km": dist,
                "pace": fmt_pace_range(*paces[wtype]) if wtype in ("easy", "long") else fmt_pace(paces[wtype][0]),
                "detail": detail,
                "hr_zone": workout_hr(wtype),
                "note": {"easy": "轻松跑", "tempo": "节奏跑", "interval": "间歇训练", "long": "长距离慢跑"}[wtype],
            })

        # 修正 day 分布，让训练日更合理
        day_map = {
            3: ["周二", "周四", "周六"],
            4: ["周一", "周三", "周五", "周六"],
            5: ["周一", "周二", "周四", "周五", "周六"],
            6: ["周一", "周二", "周三", "周四", "周五", "周六"],
        }
        for i, wk in enumerate(workouts):
            wk["day"] = day_map[weekly_days][i]

        actual_km = round(sum(w["distance_km"] for w in workouts), 1)
        weeks_data.append({
            "week": w,
            "phase": phase,
            "focus": focus,
            "workouts": workouts,
            "weekly_km": actual_km,
            "deload": is_deload,
        })

    return weeks_data, paces


def check_prerequisites(data):
    """检查阶段4前置条件：阶段1/2/3 必须完成。返回 (ok, missing[])。"""
    missing = []
    if "stage1_motivation" not in data or not data["stage1_motivation"].get("primary_goal"):
        missing.append("阶段1（目标诊断）")
    if "stage2_screening" not in data:
        missing.append("阶段2（身体筛查）")
    else:
        result = data["stage2_screening"].get("screening_result")
        if result == "hold":
            return False, ["阶段2筛查结论为 HOLD，需先解决健康风险："
                           + "; ".join(data["stage2_screening"].get("hold_flags", []))]
    if "stage3_baselines" not in data or not data["stage3_baselines"]:
        missing.append("阶段3（基线测试）")
    return len(missing) == 0, missing


def decide_plan_type(data):
    """基于前三阶段综合决策计划类型。返回 (plan_type, weekly_days, target_time, constraints)。"""
    goal = data["stage1_motivation"].get("primary_goal", "")
    screening = data["stage2_screening"]
    screening_result = screening.get("screening_result", "pass")
    screening_notes = screening.get("screening_notes", [])
    bmi = screening.get("bmi")
    running_exp = screening.get("running_experience", "none")

    # 阶段3 体能评级
    baseline_analysis = data.get("stage3_analysis", {})
    fitness = baseline_analysis.get("baseline_fitness", "moderate")
    cadence_low = "步频" in "".join(baseline_analysis.get("key_findings", [])) and "低" in "".join(baseline_analysis.get("key_findings", []))
    aerobic_weak = any("有氧基础薄弱" in f or "有氧耐力待提升" in f for f in baseline_analysis.get("key_findings", []))

    # 决策计划类型
    target_time = data["stage1_motivation"].get("target_time")

    if "减重" in goal or "健康" in goal:
        if (bmi and bmi >= 28) or fitness == "low" or running_exp == "none":
            plan_type = "couch-to-5k"
        else:
            plan_type = "maintenance"
    elif "5K" in goal:
        if fitness == "low" or running_exp == "none":
            plan_type = "couch-to-5k"
        else:
            plan_type = "5k-race"
    elif "半马" in goal or "half" in goal.lower():
        if fitness in ("low",) or running_exp == "none":
            plan_type = "couch-to-5k"  # 先打基础
        elif fitness == "moderate":
            plan_type = "half-marathon"
        else:
            plan_type = "half-marathon"
    elif "全马" in goal or "marathon" in goal.lower():
        if fitness in ("low", "moderate") or running_exp != "regular":
            plan_type = "half-marathon"  # 不建议直接上全马
        else:
            plan_type = "marathon"
    elif "PB" in goal or "刷" in goal:
        plan_type = "5k-race"
    else:
        plan_type = "maintenance"

    # 约束
    constraints = {
        "cadence_drill": cadence_low,
        "aerobic_emphasis": aerobic_weak,
        "strength_days": screening_result == "caution" or any("力量" in n for n in screening_notes),
        "walk_run_start": (bmi and bmi >= 28) or fitness == "low",
        "max_weekly_days": 3 if screening_result == "caution" and any("膝" in n or "跟腱" in n or "足" in n for n in screening_notes) else 6,
        "volume_increment": 0.08 if screening_result == "caution" else 0.10,
    }
    return plan_type, target_time, constraints


def build_plan_v2(plan_type, weekly_days, target_time, constraints):
    """基于计划类型与约束生成计划。"""
    cfg = PLAN_TYPES[plan_type]
    weeks = cfg["default_weeks"]
    base_km = cfg["base_km"]
    long_cap = cfg["long_cap"]
    walk_run = cfg.get("walk_run", False)
    vol_inc = constraints["volume_increment"]

    # 配速：优先用基线分析中的，否则用默认
    paces = estimate_paces(target_time, "beginner" if walk_run else "intermediate")

    weeks_data = []
    current_km = base_km * 0.7

    # 决定每周课表类型
    if walk_run:
        # 走跑结合计划：走跑 + 力量 + 长走
        template_types = ["walk-run", "strength", "walk-run", "walk-run"][:weekly_days]
    else:
        template_types = WEEKLY_TEMPLATES.get(weekly_days, WEEKLY_TEMPLATES[4])[:]
        # 若需步频专项，替换一个 easy
        if constraints.get("cadence_drill") and "easy" in template_types:
            idx = template_types.index("easy")
            template_types[idx] = "cadence"

    day_map = {
        3: ["周二", "周四", "周六"],
        4: ["周一", "周三", "周五", "周六"],
        5: ["周一", "周二", "周四", "周五", "周六"],
        6: ["周一", "周二", "周三", "周四", "周五", "周六"],
    }
    days = day_map.get(weekly_days, day_map[4])

    for w in range(1, weeks + 1):
        progress = (w - 1) / weeks
        if progress < 0.2:
            phase = "适应期"
            focus = "建立规律与跑姿"
        elif progress < 0.5:
            phase = "基础期"
            focus = "提升有氧基础"
        elif progress < 0.8:
            phase = "进展期"
            focus = "加入强度"
        elif progress < 0.9:
            phase = "巅峰期"
            focus = "专项强度"
        else:
            phase = "减量期"
            focus = "减量保强度"

        is_deload = (w % 4 == 0 and not walk_run) or (w >= weeks - 1 and not walk_run)
        if walk_run:
            # 走跑结合计划：仅最后1周轻减量，不做周期性减量
            is_deload = (w == weeks)
        if is_deload:
            current_km = current_km * 0.75
        else:
            current_km = min(current_km * (1 + vol_inc), base_km * 1.3)
        week_km = round(current_km, 1)

        workouts = []
        for i, wtype in enumerate(template_types):
            day = days[i] if i < len(days) else days[-1]
            wo = build_workout(wtype, week_km, long_cap, is_deload, paces, constraints, walk_run, w)
            wo["day"] = day
            workouts.append(wo)

        actual_km = round(sum(w.get("distance_km", 0) or 0 for w in workouts), 1)
        weeks_data.append({
            "week": w, "phase": phase, "focus": focus,
            "workouts": workouts, "weekly_km": actual_km, "deload": is_deload,
        })

    return weeks_data, paces


def build_workout(wtype, week_km, long_cap, is_deload, paces, constraints, walk_run, week_num):
    """生成单次训练。支持新类型。"""
    factor = 0.8 if is_deload else 1.0
    hr_map = {"easy": "Z2", "tempo": "Z4", "interval": "Z5", "long": "Z2",
              "cadence": "Z2", "walk-run": "Z2", "strength": "-", "long-walk": "Z1"}
    note_map = {"easy": "轻松跑", "tempo": "节奏跑", "interval": "间歇训练", "long": "长距离慢跑",
                "cadence": "步频专项", "walk-run": "走跑结合", "strength": "力量训练", "long-walk": "长距离快走"}

    if wtype == "walk-run":
        # 走跑结合：随周数递进，跑的比例增加
        run_ratio = min(0.5 + week_num * 0.05, 1.0)
        if week_num <= 3:
            detail = "走3分钟+跑1分钟 × 6组"
        elif week_num <= 6:
            detail = "走2分钟+跑2分钟 × 6组"
        elif week_num <= 8:
            detail = "走1分钟+跑4分钟 × 5组"
        else:
            detail = "走1分钟+跑9分钟 × 3组"
        dist = round(week_km * 0.3 * factor, 1)
        return {"type": "walk-run", "distance_km": dist, "detail": detail,
                "hr_zone": "Z2", "note": "走跑结合"}

    if wtype == "strength":
        drills = ["臀桥 3×15", "靠墙静蹲 3×45秒", "侧抬腿 3×20", "提踵 3×15（含离心）", "平板支撑 3×45秒"]
        return {"type": "strength", "distance_km": 0, "detail": " / ".join(drills[:4]),
                "hr_zone": "-", "note": "力量训练"}

    if wtype == "cadence":
        dist = round(week_km * 0.22 * factor, 1)
        detail = f"热身1km + 6×30秒高步频段（目标175+）+ 慢跑恢复 + 冷身"
        return {"type": "cadence", "distance_km": dist, "detail": detail,
                "hr_zone": "Z2", "note": "步频专项"}

    if wtype == "long-walk":
        return {"type": "long-walk", "distance_km": 0, "detail": "快走40-50分钟",
                "hr_zone": "Z1", "note": "长距离快走"}

    # 标准类型
    dist = workout_distance(wtype, week_km, long_cap, is_deload)
    detail = workout_detail(wtype, paces, "beginner" if walk_run else "intermediate")
    return {"type": wtype, "distance_km": dist, "detail": detail,
            "pace": fmt_pace_range(*paces[wtype]) if wtype in ("easy", "long") else fmt_pace(paces[wtype][0]),
            "hr_zone": hr_map.get(wtype, "Z2"), "note": note_map.get(wtype, "")}


def main():
    ap = argparse.ArgumentParser(description="生成跑步周期训练计划（阶段4）")
    ap.add_argument("--profile", action="store_true", help="从 runner-data.json 读取前三阶段数据自动决策")
    ap.add_argument("--plan-type", default=None, choices=list(PLAN_TYPES.keys()))
    ap.add_argument("--goal", default=None, choices=list(GOAL_CONFIG.keys()), help="（旧模式兼容）")
    ap.add_argument("--level", default="intermediate")
    ap.add_argument("--weeks", type=int, default=None)
    ap.add_argument("--weekly-days", type=int, default=4, dest="weekly_days")
    ap.add_argument("--target-time", default=None, dest="target_time")
    ap.add_argument("--output", default="runner-data.json")
    args = ap.parse_args()

    p = Path(args.output)
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    if args.profile:
        # 前置条件检查
        ok, missing = check_prerequisites(data)
        if not ok:
            print("❌ 无法生成计划，缺少前置阶段：")
            for m in missing:
                print(f"   - {m}")
            print("\n请先完成前三阶段再生成训练计划。")
            sys.exit(1)

        plan_type, target_time, constraints = decide_plan_type(data)
        weekly_days = min(args.weekly_days, constraints["max_weekly_days"])
        weeks_data, paces = build_plan_v2(plan_type, weekly_days, target_time, constraints)

        # 输出约束适配说明
        print("✅ 训练计划已生成（基于前三阶段诊断）")
        print(f"   计划类型: {plan_type} | 每周 {weekly_days} 天 | 周期 {len(weeks_data)} 周")
        print(f"   约束适配:")
        if constraints["walk_run_start"]:
            print(f"   - 走跑结合起步（体能/体重因素）")
        if constraints["cadence_drill"]:
            print(f"   - 含步频专项（步频偏低）")
        if constraints["aerobic_emphasis"]:
            print(f"   - 有氧基础薄弱，E跑占比提升至80%+")
        if constraints["strength_days"]:
            print(f"   - 含力量训练日（伤病/筛查约束）")
        print(f"   - 跑量递进上限: {constraints['volume_increment']*100:.0f}%/周")

        data["stage4_plan"] = {
            "created_at": datetime.now().isoformat(),
            "plan_type": plan_type,
            "weekly_days": weekly_days,
            "constraints": constraints,
            "weeks": weeks_data,
        }
    else:
        # 旧模式（手动指定）
        if args.plan_type:
            plan_type = args.plan_type
            constraints = {"volume_increment": 0.10, "walk_run_start": plan_type == "couch-to-5k",
                           "cadence_drill": False, "aerobic_emphasis": False, "strength_days": False, "max_weekly_days": 6}
            target_time = args.target_time
            weeks_data, paces = build_plan_v2(plan_type, args.weekly_days, target_time, constraints)
        else:
            # 旧 goal 模式
            goal = args.goal or "fitness"
            plan_type = "maintenance" if goal == "fitness" else goal.lower()
            plan_type = plan_type.replace("5k", "5k-race")
            constraints = {"volume_increment": 0.10, "walk_run_start": False,
                           "cadence_drill": False, "aerobic_emphasis": False, "strength_days": False, "max_weekly_days": 6}
            target_time = args.target_time
            weeks_data, paces = build_plan_v2(plan_type, args.weekly_days, target_time, constraints)

        print(f"✅ 训练计划已生成并写入 {args.output}")
        print(f"   计划类型: {plan_type} | 每周 {args.weekly_days} 天")
        data["stage4_plan"] = {
            "created_at": datetime.now().isoformat(),
            "plan_type": plan_type,
            "weekly_days": args.weekly_days,
            "constraints": constraints,
            "weeks": weeks_data,
        }

    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(w["weekly_km"] for w in weeks_data)
    print(f"   配速: 轻松 {fmt_pace_range(*paces['easy'])} | 节奏 {fmt_pace(paces['tempo'][0])}")
    print(f"   周期总跑量: {total:.1f} km")
    for w in weeks_data:
        tag = " [减量]" if w["deload"] else ""
        print(f"   W{w['week']:>2} {w['phase']} {w['weekly_km']:>5.1f} km{tag}")


if __name__ == "__main__":
    main()
