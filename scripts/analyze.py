#!/usr/bin/env python3
"""
分析跑步日志。
Usage:
    python3 analyze.py --range 4w --file runner-data.json
    python3 analyze.py --month 2026-06 --file runner-data.json
    python3 analyze.py --plan-progress --file runner-data.json
"""
import argparse, json, sys
from datetime import datetime, timedelta, date
from collections import defaultdict
from pathlib import Path


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def load(file):
    p = Path(file)
    if not p.exists():
        print(f"❌ 文件不存在: {file}")
        sys.exit(1)
    return json.loads(p.read_text(encoding="utf-8"))


def analyze_range(data, weeks):
    logs = data.get("logs", [])
    if not logs:
        print("暂无日志记录。")
        return

    today = date.today()
    start = today - timedelta(weeks=weeks)
    in_range = [l for l in logs if parse_date(l["date"]) >= start]

    if not in_range:
        print(f"近 {weeks} 周无记录。")
        return

    # 按周分组
    week_groups = defaultdict(list)
    for l in in_range:
        d = parse_date(l["date"])
        week_idx = (d - start).days // 7
        week_groups[week_idx].append(l)

    print(f"## 近 {weeks} 周分析（共 {len(in_range)} 次训练）\n")
    print("| 周 | 跑量 | 训练次数 | 平均配速 | 平均心率 | 平均RPE |")
    print("|---|---|---|---|---|---|")
    weekly_kms = []
    for i in range(weeks):
        grp = week_groups.get(i, [])
        if not grp:
            print(f"| W{i+1} | 0 km | 0 | - | - | - |")
            weekly_kms.append(0)
            continue
        km = sum(l.get("distance_km", 0) or 0 for l in grp)
        n = len(grp)
        # 平均配速
        paces = [l["pace"] for l in grp if l.get("pace")]
        avg_hr = [l["avg_hr"] for l in grp if l.get("avg_hr")]
        rpes = [l["rpe"] for l in grp if l.get("rpe")]
        weekly_kms.append(km)
        avg_pace = "-"
        if paces:
            total_secs = sum(int(p.split(":")[0]) * 60 + int(p.split(":")[1]) for p in paces)
            avg_pace = f"{total_secs // len(paces) // 60}:{(total_secs // len(paces)) % 60:02d}"
        avg_hr_str = f"{sum(avg_hr)//len(avg_hr)}" if avg_hr else "-"
        avg_rpe = f"{sum(rpes)/len(rpes):.1f}" if rpes else "-"
        print(f"| W{i+1} | {km:.1f} km | {n} | {avg_pace} | {avg_hr_str} | {avg_rpe} |")

    total = sum(weekly_kms)
    print(f"\n**总跑量**: {total:.1f} km | **周均**: {total/weeks:.1f} km")

    # 10% 原则检查
    print("\n### 跑量递进检查")
    for i in range(1, len(weekly_kms)):
        if weekly_kms[i-1] > 0 and weekly_kms[i] > 0:
            inc = (weekly_kms[i] - weekly_kms[i-1]) / weekly_kms[i-1] * 100
            if inc > 10:
                print(f"⚠️ W{i+1} 较 W{i} 增长 {inc:.0f}%，超过 10% 原则，注意伤病风险")
            elif inc < -20 and i % 4 != 3:
                print(f"ℹ️ W{i+1} 下降 {abs(inc):.0f}%，若非减量周需留意训练连续性")


def analyze_month(data, month_str):
    logs = data.get("logs", [])
    in_month = [l for l in logs if l["date"].startswith(month_str)]
    if not in_month:
        print(f"{month_str} 无记录。")
        return
    km = sum(l.get("distance_km", 0) or 0 for l in in_month)
    dur = sum(l.get("duration_min", 0) or 0 for l in in_month)
    print(f"## {month_str} 汇总\n")
    print(f"- 训练次数: {len(in_month)}")
    print(f"- 总跑量: {km:.1f} km")
    print(f"- 总时长: {dur:.0f} 分钟 ({dur/60:.1f} 小时)")
    print(f"- 平均单次: {km/len(in_month):.1f} km")
    # RPE 趋势
    rpes = [l["rpe"] for l in in_month if l.get("rpe")]
    if rpes:
        print(f"- 平均 RPE: {sum(rpes)/len(rpes):.1f}/10")
        if sum(rpes)/len(rpes) >= 7.5:
            print("⚠️ 本月平均劳累度偏高，建议增加恢复")


def plan_progress(data):
    plan = data.get("plan")
    logs = data.get("logs", [])
    if not plan:
        print("暂无训练计划。")
        return
    weeks = plan.get("weeks", [])
    today = date.today()
    created = parse_date(plan["created_at"][:10])
    elapsed_days = (today - created).days
    elapsed_weeks = elapsed_days // 7 + 1

    print(f"## 训练计划执行情况\n")
    print(f"- 计划开始: {plan['created_at'][:10]}")
    print(f"- 已过去: {elapsed_weeks} 周 / 共 {len(weeks)} 周")
    print(f"- 已记录训练: {len(logs)} 次\n")

    # 简单对照：本周应训练内容
    current_week_idx = elapsed_weeks - 1
    if 0 <= current_week_idx < len(weeks):
        w = weeks[current_week_idx]
        print(f"### 本周（第 {w['week']} 周 - {w.get('phase','')}）")
        print(f"焦点: {w.get('focus','')}")
        print("| 日期 | 类型 | 计划距离 | 计划配速 |")
        print("|---|---|---|---|")
        for wo in w["workouts"]:
            print(f"| {wo['day']} | {wo['note']} | {wo['distance_km']} km | {wo['pace']} |")
        print(f"\n本周计划跑量: {w['weekly_km']} km")


def analyze_baseline(data):
    """阶段3 基线分析：标定心率区间、配速区间、步频评估、心率漂移、体能评级。"""
    baselines = data.get("stage3_baselines", [])
    screening = data.get("stage2_screening", {})
    if not baselines:
        print("⚠️ 无基线测试数据，请先完成阶段3基线测试。")
        print("测试方式：进行一次 1km 慢跑或 30分钟走跑结合，记录距离/时长/心率/步频/RPE。")
        print("记录命令：python3 log_run.py --date ... --baseline ...")
        return

    print("=" * 50)
    print("阶段3 基线分析")
    print("=" * 50)

    age = screening.get("age", 30)
    est_hr_max = screening.get("estimated_hr_max") or round(208 - 0.7 * age)
    resting_hr = screening.get("resting_hr", 65)

    # 找最长的一次测试作为主基线
    main = max(baselines, key=lambda b: b.get("duration_min", 0))
    avg_hr = main.get("avg_hr")
    max_hr = main.get("max_hr", avg_hr)
    cadence = main.get("cadence")
    pace = main.get("pace")
    rpe = main.get("rpe")
    distance = main.get("distance_km", 0)
    duration = main.get("duration_min", 0)

    print(f"\n主基线测试: {main.get('date')} | {distance}km | {duration}min | 配速{pace} | 心率{avg_hr} | 步频{cadence} | RPE{rpe}")

    # 1. 心率区间标定
    print("\n### 心率区间标定")
    if max_hr and max_hr > 0:
        measured_max = max_hr
        print(f"实测最高心率: {measured_max}（估算: {est_hr_max}）")
        hr_max = max(measured_max, est_hr_max - 5)  # 取较高值
    else:
        hr_max = est_hr_max
        print(f"无实测最高心率，使用估算: {hr_max}")

    # 5 区划分（Karvonen 储备心率法，考虑静息心率）
    if resting_hr:
        hrr = hr_max - resting_hr
        z1_lo, z1_hi = resting_hr, int(resting_hr + hrr * 0.5)
        z2_lo, z2_hi = z1_hi, int(resting_hr + hrr * 0.6)
        z3_lo, z3_hi = z2_hi, int(resting_hr + hrr * 0.7)
        z4_lo, z4_hi = z3_hi, int(resting_hr + hrr * 0.8)
        z5_lo = z4_hi
    else:
        z1_lo, z1_hi = 0, int(hr_max * 0.65)
        z2_lo, z2_hi = z1_hi, int(hr_max * 0.75)
        z3_lo, z3_hi = z2_hi, int(hr_max * 0.82)
        z4_lo, z4_hi = z3_hi, int(hr_max * 0.89)
        z5_lo = z4_hi

    print(f"| 区间 | 心率 | 主观感受 |")
    print(f"|---|---|---|")
    print(f"| Z1 恢复 | <{z2_lo} | 轻松自如 |")
    print(f"| Z2 有氧 | {z2_lo}-{z2_hi} | 能说完整句子 |")
    print(f"| Z3 马拉松 | {z2_hi}-{z3_hi} | 能说短句 |")
    print(f"| Z4 阈值 | {z3_hi}-{z4_hi} | 只能说几个词 |")
    print(f"| Z5 间歇 | >{z4_hi} | 无法说话 |")

    # 2. 配速区间推算
    print("\n### 配速区间推算")
    if pace:
        pace_secs = int(pace.split(":")[0]) * 60 + int(pace.split(":")[1])
        # 基线配速作为 Z3 锚点
        easy_pace = pace_secs * 1.25
        tempo_pace = pace_secs * 1.03
        interval_pace = pace_secs * 0.93
        print(f"基于基线配速 {pace}（Z3锚点）：")
        print(f"| 类型 | 配速 |")
        print(f"|---|---|")
        print(f"| Z2 轻松跑 | {int(easy_pace//60)}:{int(easy_pace%60):02d}-{int((easy_pace+30)//60)}:{int((easy_pace+30)%60):02d} |")
        print(f"| Z3 马拉松 | {pace} |")
        print(f"| Z4 节奏跑 | {int(tempo_pace//60)}:{int(tempo_pace%60):02d} |")
        print(f"| Z5 间歇 | {int(interval_pace//60)}:{int(interval_pace%60):02d} |")

    # 3. 步频评估
    print("\n### 步频评估")
    cadence_findings = []
    if cadence:
        if cadence < 160:
            print(f"⚠️ 步频 {cadence} spm 严重偏低，伤风险高，需专项改善")
            cadence_findings.append(f"步频{cadence}严重偏低，加入步频专项，目标先到170")
        elif cadence < 170:
            print(f"⚠️ 步频 {cadence} spm 偏低，建议提升至 170-180")
            cadence_findings.append(f"步频{cadence}偏低，加入步频专项，目标175+")
        elif cadence <= 185:
            print(f"✅ 步频 {cadence} spm 理想区间")
        else:
            print(f"ℹ️ 步频 {cadence} spm 偏高，关注步幅是否过小")

    # 4. 心率-配速关系 / 有氧基础
    print("\n### 有氧基础评估")
    aerobic_findings = []
    fitness = "moderate"
    if pace and avg_hr:
        pace_secs = int(pace.split(":")[0]) * 60 + int(pace.split(":")[1])
        # 若 Z2 心率下配速 > 7:00（420秒），有氧基础薄弱
        z2_mid = (z2_lo + z2_hi) // 2
        if avg_hr > z2_mid and pace_secs > 420:
            fitness = "low"
            print(f"⚠️ 测试心率 {avg_hr} 已高于Z2中段，且配速 {pace} > 7:00，有氧基础薄弱")
            print(f"   → 阶段4 起步以时间为主（不追求距离），E跑占比提升至80%+")
            aerobic_findings.append("有氧基础薄弱，Z2心率下配速>7:00，阶段4以时间为目标，E跑占比80%+")
        elif pace_secs < 360 and avg_hr < z2_hi:
            fitness = "good"
            print(f"✅ 配速 {pace} 下心率 {avg_hr} 在Z2内，有氧基础良好")
        else:
            fitness = "moderate"
            print(f"ℹ️ 有氧基础中等，可正常训练")

    # 5. 心率漂移（若有多次记录或单次时长信息）
    print("\n### 心率漂移")
    drift_findings = []
    if len(baselines) >= 1 and main.get("duration_min", 0) >= 20:
        # 简化：若无分段数据，用 RPE 与心率关系推断
        if rpe and rpe >= 7 and avg_hr and avg_hr > z3_hi:
            print(f"⚠️ RPE={rpe} 偏高且心率 {avg_hr} 进入Z4+，提示有氧耐力待提升")
            print(f"   → 单次连续跑步时长暂限 40 分钟")
            drift_findings.append("有氧耐力待提升，心率漂移明显，单次时长暂限40分钟")

    # 综合体能评级
    print(f"\n### 综合体能评级: 【{fitness.upper()}】")

    # 写入分析结果
    data["stage3_analysis"] = {
        "hr_zones_calibrated": True,
        "max_hr_estimate": hr_max,
        "hr_zones": {"Z1": f"<{z2_lo}", "Z2": f"{z2_lo}-{z2_hi}", "Z3": f"{z2_hi}-{z3_hi}",
                     "Z4": f"{z3_hi}-{z4_hi}", "Z5": f">{z4_hi}"},
        "cadence_assessment": f"{cadence}spm" if cadence else "无数据",
        "baseline_fitness": fitness,
        "key_findings": cadence_findings + aerobic_findings + drift_findings,
    }


def main():
    ap = argparse.ArgumentParser(description="分析跑步日志 / 阶段3基线分析")
    ap.add_argument("--range", dest="range_weeks", help="如 4w")
    ap.add_argument("--month", help="如 2026-06")
    ap.add_argument("--plan-progress", action="store_true", dest="plan_progress")
    ap.add_argument("--baseline", action="store_true", help="阶段3基线分析模式")
    ap.add_argument("--file", default="runner-data.json")
    args = ap.parse_args()

    data = load(args.file)
    if args.baseline:
        analyze_baseline(data)
        # 写回文件
        Path(args.file).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n✅ 基线分析已写入 {args.file}")
    elif args.range_weeks:
        w = int(args.range_weeks.rstrip("w"))
        analyze_range(data, w)
    elif args.month:
        analyze_month(data, args.month)
    elif args.plan_progress:
        plan_progress(data)
    else:
        analyze_range(data, 4)


if __name__ == "__main__":
    main()
