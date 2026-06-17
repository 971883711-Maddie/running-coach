#!/usr/bin/env python3
"""
把训练计划导出为 iCal 日历文件，可导入手机日历。

Usage:
    python3 export_ical.py --file runner-data.json --output plan.ics
    python3 export_ical.py --file runner-data.json --start-date 2026-06-23 --output plan.ics
"""
import argparse, json, sys
from datetime import datetime, timedelta, date
from pathlib import Path


WEEKDAY_MAP = {"周一": 0, "周二": 1, "周三": 2, "周四": 3, "周五": 4, "周六": 5, "周日": 6}


def escape_ical(text):
    """转义 iCal 特殊字符。"""
    if not text:
        return ""
    return (text.replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\n", "\\n"))


def fmt_dt(dt):
    """datetime → iCal UTC 格式 YYYYMMDDTHHMMSSZ"""
    return dt.strftime("%Y%m%dT%H%M%SZ")


def build_event(uid, dt_start, duration_min, summary, description, alarm_min=30):
    """构建单个 VEVENT。"""
    dt_end = dt_start + timedelta(minutes=duration_min)
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{fmt_dt(datetime.utcnow())}",
        f"DTSTART:{fmt_dt(dt_start)}",
        f"DTEND:{fmt_dt(dt_end)}",
        f"SUMMARY:{escape_ical(summary)}",
        f"DESCRIPTION:{escape_ical(description)}",
    ]
    if alarm_min:
        lines.extend([
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{escape_ical('训练提醒: ' + summary)}",
            f"TRIGGER:-PT{alarm_min}M",
            "END:VALARM",
        ])
    lines.append("END:VEVENT")
    return lines


def parse_start_date(start_str, plan_created):
    """解析起始日期。默认用计划创建日期所在周的周一。"""
    if start_str:
        return datetime.strptime(start_str, "%Y-%m-%d").date()
    if plan_created:
        created = datetime.fromisoformat(plan_created.replace("Z", "+00:00")).date()
    else:
        created = date.today()
    # 回到本周一
    return created - timedelta(days=created.weekday())


def main():
    ap = argparse.ArgumentParser(description="导出训练计划为 iCal 日历")
    ap.add_argument("--file", default="runner-data.json")
    ap.add_argument("--output", default="training-plan.ics")
    ap.add_argument("--start-date", default=None, help="计划起始日期 YYYY-MM-DD（默认用计划创建日所在周一）")
    ap.add_argument("--duration", type=int, default=60, help="默认单次训练时长(分钟)，力量日默认45")
    ap.add_argument("--alarm", type=int, default=30, help="提前提醒分钟数，0=不提醒")
    args = ap.parse_args()

    p = Path(args.file)
    if not p.exists():
        print(f"❌ 文件不存在: {args.file}")
        sys.exit(1)
    data = json.loads(p.read_text(encoding="utf-8"))

    plan = data.get("stage4_plan") or data.get("plan")
    if not plan or not plan.get("weeks"):
        print("❌ 无训练计划，请先完成阶段4生成计划。")
        sys.exit(1)

    plan_created = plan.get("created_at", "")
    start_date = parse_start_date(args.start_date, plan_created)

    events = []
    uid_counter = 0
    total_workouts = 0

    for week in plan["weeks"]:
        week_num = week["week"]
        phase = week.get("phase", "")
        focus = week.get("focus", "")
        week_start = start_date + timedelta(weeks=week_num - 1)

        for wo in week.get("workouts", []):
            day_name = wo.get("day", "")
            weekday = WEEKDAY_MAP.get(day_name, 0)
            workout_date = week_start + timedelta(days=weekday)
            # 默认早上 6:30 开始
            dt_start = datetime.combine(workout_date, datetime.min.time()) + timedelta(hours=6, minutes=30)

            wo_type = wo.get("type", "")
            note = wo.get("note", wo_type)
            detail = wo.get("detail", "")
            pace = wo.get("pace", "")
            hr_zone = wo.get("hr_zone", "")
            dist = wo.get("distance_km", 0)

            # 时长：力量日45min，走跑结合按内容估，其余默认
            if wo_type == "strength":
                duration = 45
            elif "走3分钟+跑1分钟" in detail:
                duration = 30
            elif "走2分钟+跑2分钟" in detail:
                duration = 30
            elif "走1分钟+跑4分钟" in detail:
                duration = 30
            elif "走1分钟+跑9分钟" in detail:
                duration = 35
            elif "快走" in detail:
                duration = 45
            elif dist and dist > 0:
                # 按配速估算（默认6:00/km）
                pace_secs = 360
                if pace and "-" in pace:
                    try:
                        p_lo = pace.split("-")[0]
                        pace_secs = int(p_lo.split(":")[0]) * 60 + int(p_lo.split(":")[1])
                    except (ValueError, IndexError):
                        pass
                duration = max(int(dist * pace_secs / 60) + 10, 30)  # +10分钟热身冷身
            else:
                duration = args.duration

            summary = f"W{week_num} {note}"
            desc_parts = [f"第{week_num}周 | {phase} | 焦点: {focus}"]
            if dist:
                desc_parts.append(f"距离: {dist} km")
            if pace:
                desc_parts.append(f"配速: {pace}")
            if hr_zone and hr_zone != "-":
                desc_parts.append(f"心率区间: {hr_zone}")
            if detail:
                desc_parts.append(f"内容: {detail}")
            description = "\n".join(desc_parts)

            uid = f"run-w{week_num}-{uid_counter}@running-coach"
            events.extend(build_event(uid, dt_start, duration, summary, description, args.alarm))
            uid_counter += 1
            total_workouts += 1

    # 组装 iCal
    ical_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Running Coach//Training Plan//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:跑步训练计划",
        "X-WR-TIMEZONE:Asia/Shanghai",
    ] + events + ["END:VCALENDAR"]

    out_path = Path(args.output)
    out_path.write_text("\r\n".join(ical_lines), encoding="utf-8")

    print(f"✅ 训练计划已导出为 iCal 日历")
    print(f"   文件: {args.output}")
    print(f"   总训练次数: {total_workouts}")
    print(f"   起始日期: {start_date.strftime('%Y-%m-%d')}（周一）")
    print(f"   计划周期: {len(plan['weeks'])} 周")
    print(f"\n   导入方法:")
    print(f"   - iPhone: 用邮件把 {args.output} 发给自己，点击附件即可导入日历")
    print(f"   - 安卓: 导入 Google Calendar 或用日历App打开")
    print(f"   - Outlook: 双击文件或拖入日历")


if __name__ == "__main__":
    main()
