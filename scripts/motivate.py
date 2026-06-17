#!/usr/bin/env python3
"""
阶段1 目标诊断：对话式收集跑者动机与目标，写入 stage1_motivation。

支持两种用法：
  交互式（推荐，逐项问答）：
    python3 motivate.py --output runner-data.json
  一次性传入（已知所有信息时）：
    python3 motivate.py --goal "减重" --success "3个月减5kg能连续跑30分钟" \
        --timeframe "3个月" --attempts "去年膝盖疼放弃" --barriers "怕膝盖再受伤" \
        --secondary "改善睡眠" --output runner-data.json
"""
import argparse, json, sys
from pathlib import Path


# 目标选项（value → 显示标签）
GOAL_OPTIONS = [
    ("减重", "减重 / 控制体重"),
    ("健康改善", "改善健康（血压/血糖/睡眠等）"),
    ("减压", "减压 / 心理调节"),
    ("5K完赛", "5公里完赛"),
    ("10K完赛", "10公里完赛"),
    ("半马", "半程马拉松完赛"),
    ("全马", "全程马拉松完赛"),
    ("刷PB", "已有完赛经验，想刷个人最好成绩"),
    ("健身", "仅健身/保持运动习惯"),
    ("社交跑", "社交跑步（跑团/活动）"),
]

# 目标 → 影响后续阶段的提示
GOAL_HINTS = {
    "减重": "后续阶段2需严查BMI与关节；阶段3起步行跑结合",
    "健康改善": "后续阶段2必查慢病史；关注血压静息心率变化",
    "减压": "强调规律性而非强度，可放宽进度要求",
    "5K完赛": "适合新手，8-12周可达，走跑结合渐进",
    "10K完赛": "需一定有氧基础，10-12周",
    "半马": "需3-6月有氧基础，阶段2严查下肢，阶段3评估长距离耐受",
    "全马": "需1年以上规律跑步，阶段2全面筛查，未达标直接劝退",
    "刷PB": "已有完赛经验，阶段3重在精确配速区间标定",
    "健身": "保持运动习惯，强度自由",
    "社交跑": "以参与为主，强度灵活",
}


def prompt_choice(prompt, options, allow_multi=False):
    """带编号的选项提示，返回选中的 value。"""
    print(f"\n{prompt}")
    for i, (val, label) in enumerate(options, 1):
        print(f"  {i}. {label}")
    while True:
        raw = input(f"请输入{'编号(可多选,逗号分隔)' if allow_multi else '编号'}: ").strip()
        try:
            if allow_multi:
                idxs = [int(x.strip()) for x in raw.split(",")]
                return [options[i - 1][0] for i in idxs if 1 <= i <= len(options)]
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1][0]
            print(f"  请输入 1-{len(options)} 之间的数字")
        except ValueError:
            print(f"  请输入有效数字")


def prompt_text(prompt, default="", required=True, multiline_hint=False):
    """文本输入。required=True 时空输入会重问。"""
    suffix = "" if not multiline_hint else "（可多行，输空行结束）"
    while True:
        val = input(f"\n{prompt}{suffix}: ").strip()
        if val or not required:
            return val or default
        print("  此项必填，请输入内容")


def prompt_optional(prompt):
    """可选项，直接回车跳过。"""
    return input(f"\n{prompt}（可跳过）: ").strip() or "无"


def collect_interactive():
    print("=" * 55)
    print("  阶段1 目标诊断")
    print("  先搞清楚「为什么跑、成功标准是什么」")
    print("=" * 55)

    # 1. 主要目标
    primary = prompt_choice("① 你跑步的主要目标是？", GOAL_OPTIONS)
    print(f"   → 已选: {primary}")
    hint = GOAL_HINTS.get(primary, "")
    if hint:
        print(f"   💡 提示: {hint}")

    # 2. 次要目标
    secondary = prompt_optional("② 有没有次要目标？比如改善睡眠、控制血压等")

    # 3. 成功标准
    print("\n③ 怎样算成功？请给出可衡量的标准。")
    print("   例：3个月减重5kg / 半马跑进2小时 / 能连续跑30分钟不喘")
    success = prompt_text("   你的成功标准", required=True)

    # 4. 时间框架
    timeframe = prompt_text("④ 希望多久内达成？（如3个月、半年）", required=True)

    # 5. 过往尝试
    print("\n⑤ 之前试过跑步吗？")
    past_attempts = prompt_text("   过往尝试的情况与结果（没试过可写「无」）", required=True)

    # 6. 障碍
    print("\n⑥ 你担心什么会阻碍你坚持？")
    print("   常见：工作忙 / 怕受伤 / 没动力 / 天气 / 不会安排")
    barriers = prompt_text("   你的顾虑", required=True)

    return {
        "primary_goal": primary,
        "secondary_goal": secondary,
        "success_criteria": success,
        "timeframe": timeframe,
        "past_attempts": past_attempts,
        "barriers": barriers,
    }


def collect_args(args):
    """从命令行参数直接构造。"""
    if not args.goal:
        print("交互模式或 --goal 必填其一")
        sys.exit(1)
    return {
        "primary_goal": args.goal,
        "secondary_goal": args.secondary or "无",
        "success_criteria": args.success or "",
        "timeframe": args.timeframe or "",
        "past_attempts": args.attempts or "无",
        "barriers": args.barriers or "",
    }


def main():
    ap = argparse.ArgumentParser(description="阶段1 目标诊断")
    ap.add_argument("--goal", default=None, choices=[g[0] for g in GOAL_OPTIONS],
                    help="主要目标（不填则进入交互模式）")
    ap.add_argument("--secondary", default=None, help="次要目标")
    ap.add_argument("--success", default=None, help="成功标准")
    ap.add_argument("--timeframe", default=None, help="时间框架")
    ap.add_argument("--attempts", default=None, help="过往尝试")
    ap.add_argument("--barriers", default=None, help="顾虑障碍")
    ap.add_argument("--output", default="runner-data.json")
    args = ap.parse_args()

    # 决定交互 or 命令行
    if args.goal and args.success and args.timeframe:
        data = collect_args(args)
    else:
        data = collect_interactive()

    # 写入
    p = Path(args.output)
    existing = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    existing["stage1_motivation"] = data
    p.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    # 复述确认
    print("\n" + "=" * 55)
    print("  阶段1 目标诊断已完成")
    print("=" * 55)
    print(f"\n  主要目标: {data['primary_goal']}")
    if data["secondary_goal"] != "无":
        print(f"  次要目标: {data['secondary_goal']}")
    print(f"  成功标准: {data['success_criteria']}")
    print(f"  时间框架: {data['timeframe']}")
    print(f"  过往尝试: {data['past_attempts']}")
    print(f"  顾虑障碍: {data['barriers']}")

    hint = GOAL_HINTS.get(data["primary_goal"], "")
    if hint:
        print(f"\n  💡 后续提示: {hint}")
    print(f"\n  数据已写入: {args.output}")
    print(f"  下一步: 运行 screen.py 进入阶段2身体筛查")
    print(f"    python3 screen.py --age <年龄> --gender <male/female> "
          f"--height <cm> --weight <kg> ... --output {args.output}")


if __name__ == "__main__":
    main()
