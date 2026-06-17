#!/usr/bin/env python3
"""
阶段2 身体筛查：评估跑者能否开始跑步、有何约束。
读取/写入 runner-data.json 的 stage2_screening 字段。

Usage:
    python3 screen.py --age 35 --gender male --height 175 --weight 78 \
        --resting-hr 65 --injuries '右膝:髌骨软化:已康复6个月:中' \
        --medical '无' --running-exp none --output runner-data.json
"""
import argparse, json, sys
from pathlib import Path


def calc_bmi(height_cm, weight_kg):
    if not height_cm or not weight_kg:
        return None
    return round(weight_kg / (height_cm / 100) ** 2, 1)


def estimate_hr_max(age):
    return round(208 - 0.7 * age)


def parse_injuries(s):
    """格式: 部位:问题:状态:严重度, 部位2:问题2:状态2:严重度2"""
    if not s or s.lower() in ("无", "none", ""):
        return []
    injuries = []
    for item in s.split(","):
        parts = [p.strip() for p in item.split(":")]
        if len(parts) >= 2:
            injuries.append({
                "part": parts[0],
                "issue": parts[1],
                "status": parts[2] if len(parts) > 2 else "",
                "severity": parts[3] if len(parts) > 3 else "轻"
            })
    return injuries


def parse_medical(s):
    if not s or s.lower() in ("无", "none", ""):
        return []
    return [m.strip() for m in s.split(",")]


def screen(age, gender, height, weight, resting_hr, injuries, medical, running_exp, recent_5k=None):
    """返回 (conclusion, notes[], hold_flags[])"""
    bmi = calc_bmi(height, weight)
    hr_max = estimate_hr_max(age)
    notes = []
    hold_flags = []
    caution_count = 0

    # BMI 评估
    if bmi is not None:
        if bmi >= 30:
            caution_count += 1
            notes.append(f"BMI={bmi}（肥胖），先走跑结合4周减重，减少关节冲击；同步营养干预")
        elif bmi >= 28:
            caution_count += 1
            notes.append(f"BMI={bmi}（超重偏高），建议走跑结合起步，单次≤30分钟，每周≤3次")
        elif bmi >= 25:
            notes.append(f"BMI={bmi}（略超重），可正常开始，关注配速不宜过快")
        elif bmi < 18:
            caution_count += 1
            notes.append(f"BMI={bmi}（偏瘦），先评估营养与肌肉量，不建议直接长距离")

    # 年龄 + 无运动基础
    if age and age > 55 and running_exp == "none":
        caution_count += 1
        notes.append(f"年龄{age}且无运动基础，从快走开始6周再评估转入跑步")

    # 伤病评估
    active_injuries = [i for i in injuries if "已康复" not in i.get("status", "") and "康复" not in i.get("status", "")]
    knee_issues = [i for i in injuries if "膝" in i.get("part", "") or "髌" in i.get("issue", "")]
    achilles_issues = [i for i in injuries if "跟腱" in i.get("part", "") or "跟腱" in i.get("issue", "")]
    foot_issues = [i for i in injuries if "足底" in i.get("part", "") or "足" in i.get("part", "")]

    if active_injuries:
        # 急性/未愈伤病
        severe = [i for i in active_injuries if i.get("severity") == "重"]
        if severe:
            hold_flags.append(f"存在未愈的重度伤病：{severe[0]['part']}-{severe[0]['issue']}，需先康复")
        else:
            caution_count += 1
            notes.append(f"存在未愈伤病（{'/'.join(i['part'] for i in active_injuries)}），限频限距，疼痛即停")

    if knee_issues:
        caution_count += 1
        notes.append("膝盖/髌骨伤史：避开下坡与硬地，初期限3次/周每次≤30分钟；每周加2次股四头肌与臀中肌力量")
    if achilles_issues:
        caution_count += 1
        notes.append("跟腱伤史：限频限距，每周加小腿离心训练（提踵缓慢下落3×15），避免上坡")
    if foot_issues:
        caution_count += 1
        notes.append("足部伤史：检查跑鞋足弓支撑，每日足底筋膜拉伸，晨起先活动脚踝再下地")

    # 医疗史评估
    for m in medical:
        m_lower = m.lower()
        if "高血压" in m and ("未控制" in m or ">160" in m):
            hold_flags.append("高血压未控制，必须就医评估后再开始跑步")
        elif "高血压" in m:
            caution_count += 1
            notes.append("高血压（药物控制中）：限Z2低强度，避免憋气与高强度间歇，训练前后监测血压")
        if "心绞痛" in m or "胸闷" in m or "晕厥" in m:
            hold_flags.append(f"存在心脏相关症状（{m}），需心内科评估后再开始")
        if "心律" in m:
            hold_flags.append("心律异常，需心内科评估")
        if "糖尿病" in m:
            caution_count += 1
            notes.append("糖尿病：避免空腹跑，随身携带碳水，监测血糖；优先选择餐后1-2小时运动")
        if "哮喘" in m:
            caution_count += 1
            notes.append("哮喘：随身带药，充分热身15分钟，避免寒冷干燥空气下高强度")
        if "甲亢" in m:
            caution_count += 1
            notes.append("甲亢：监测心率，避免高强度，控制后才宜跑步")
    if "妊娠" in str(medical) or "孕" in str(medical):
        hold_flags.append("妊娠期需产科医生评估后再决定运动方案")

    # 静息心率评估
    if resting_hr:
        if resting_hr > 100:
            hold_flags.append(f"静息心率{resting_hr}偏高（>100），需排查心血管问题后再开始")
        elif resting_hr > 85:
            caution_count += 1
            notes.append(f"静息心率{resting_hr}偏高，心肺功能偏弱，起步强度宜低")
        elif resting_hr < 50 and running_exp in ("none", "casual"):
            notes.append(f"静息心率{resting_hr}偏低，若无训练基础需排查是否有传导问题")
        elif resting_hr < 60:
            notes.append(f"静息心率{resting_hr}良好，心肺功能不错")

    # 结论判定
    if hold_flags:
        conclusion = "hold"
    elif caution_count >= 2:
        conclusion = "caution"
    elif caution_count == 1:
        conclusion = "caution"
    else:
        conclusion = "pass"

    return {
        "conclusion": conclusion,
        "bmi": bmi,
        "estimated_hr_max": hr_max,
        "caution_count": caution_count,
        "notes": notes,
        "hold_flags": hold_flags,
    }


def main():
    ap = argparse.ArgumentParser(description="阶段2 身体筛查")
    ap.add_argument("--age", type=int, required=True)
    ap.add_argument("--gender", choices=["male", "female"], required=True)
    ap.add_argument("--height", type=float, required=True)
    ap.add_argument("--weight", type=float, required=True)
    ap.add_argument("--resting-hr", type=int)
    ap.add_argument("--injuries", default="无", help="部位:问题:状态:严重度，多条逗号分隔")
    ap.add_argument("--medical", default="无", help="医疗史，逗号分隔")
    ap.add_argument("--running-exp", choices=["none", "casual", "regular"], default="none")
    ap.add_argument("--recent-5k", default=None)
    ap.add_argument("--exercise-history", default="")
    ap.add_argument("--output", default="runner-data.json")
    args = ap.parse_args()

    injuries = parse_injuries(args.injuries)
    medical = parse_medical(args.medical)
    result = screen(args.age, args.gender, args.height, args.weight,
                    args.resting_hr, injuries, medical, args.running_exp)

    # 写入 runner-data.json
    p = Path(args.output)
    data = {}
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
    data["stage2_screening"] = {
        "age": args.age,
        "gender": args.gender,
        "height_cm": args.height,
        "weight_kg": args.weight,
        "bmi": result["bmi"],
        "resting_hr": args.resting_hr,
        "exercise_history": args.exercise_history,
        "running_experience": args.running_exp,
        "recent_5k_pb": args.recent_5k,
        "injuries": injuries,
        "medical_flags": medical,
        "screening_result": result["conclusion"],
        "estimated_hr_max": result["estimated_hr_max"],
        "screening_notes": result["notes"],
        "hold_flags": result["hold_flags"],
    }
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # 输出
    print("=" * 50)
    print("阶段2 身体筛查结果")
    print("=" * 50)
    print(f"\nBMI: {result['bmi']}")
    print(f"估算最大心率: {result['estimated_hr_max']} bpm")
    print(f"\n筛查结论: 【{result['conclusion'].upper()}】")

    if result["hold_flags"]:
        print("\n🚫 暂缓开始（HOLD）:")
        for f in result["hold_flags"]:
            print(f"   - {f}")
        print("\n   建议先就医评估或做替代运动（快走/游泳/力量训练），待条件满足后再来。")

    if result["notes"]:
        print("\n⚠️ 约束条件:")
        for n in result["notes"]:
            print(f"   - {n}")

    if result["conclusion"] == "pass":
        print("\n✅ 可正常开始跑步训练，进入阶段3基线测试。")
    elif result["conclusion"] == "caution":
        print("\n⚠️ 可跑步但需遵守上述约束，进入阶段3基线测试（收紧测试范围）。")
    print(f"\n数据已写入: {args.output}")


if __name__ == "__main__":
    main()
