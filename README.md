# Running Coach 跑步教练 · 使用说明

> **诊断式跑步指导**——不给你一份"通用课表"就完事，而是像医生问诊一样，先搞清楚你为什么跑、身体能不能跑、适合怎么跑，再基于你的真实数据定制方案。

---

## 为什么不是"直接给我个训练计划"？

市面上 90% 的跑步 App 和攻略都是上来就甩课表："12 周半马计划，第 1 周 30 公里……"

但问题在于：

- 你 BMI 30、膝盖有过伤，第一周 30 公里可能直接让你告别跑步半年
- 你已经有马拉松完赛经验想刷 PB，通用计划的强度根本刺激不到你
- 你连自己的心率区间都不知道，计划里写的"Z2 跑"对你毫无意义

**Running Coach 的逻辑是：诊断优先于方案。** 先把你的情况摸清楚，再开方子。

---

## 四阶段流程（这是核心）

```
阶段1 目标诊断  →  阶段2 身体筛查  →  阶段3 基线测试  →  阶段4 定制计划
   为什么跑         能不能跑           现在什么水平        该怎么练
                                                    ↑
                              每次记录跑步后自动回流检测 ─┘ 动态调整
```

### 阶段1：目标诊断（5 分钟）

**要回答的问题**：你为什么想跑步？怎样算成功？

支持的目标类型：

| 目标 | 适合谁 | 后续侧重 |
|---|---|---|
| 减重 | 想通过跑步控制体重 | 严查 BMI 与关节，走跑结合起步 |
| 健康改善 | 改善血压/血糖/睡眠 | 必查慢病史 |
| 减压 | 心理调节、解压 | 重在规律性而非强度 |
| 5K 完赛 | 新手第一目标 | 8-12 周，走跑结合渐进 |
| 10K 完赛 | 有一定基础 | 10-12 周 |
| 半马 | 有 3-6 月有氧基础 | 12-16 周 |
| 全马 | 有 1 年以上规律跑步 | 16-18 周，未达标劝退 |
| 刷 PB | 已有完赛经验 | 精确标定配速区间 |

**怎么用**：

```bash
# 方式一：交互式问答（推荐第一次用）
python3 scripts/motivate.py --output runner-data.json

# 方式二：一次性传入（已知全部信息）
python3 scripts/motivate.py --goal "减重" \
  --success "3个月减5kg能连续跑30分钟" \
  --timeframe "3个月" \
  --attempts "去年膝盖疼放弃" \
  --barriers "怕膝盖再受伤" \
  --output runner-data.json
```

### 阶段2：身体筛查（3 分钟）

**要回答的问题**：你的身体能开始跑步吗？有什么风险要注意？

输入年龄、性别、身高体重（自动算 BMI）、静息心率、伤病史、医疗史，系统给出三档结论：

| 结论 | 含义 | 后续 |
|---|---|---|
| **pass** | 可以正常开始 | 进入阶段3 |
| **caution** | 可以跑，但有约束 | 给出具体限制（如限频、加力量、避下坡），进入阶段3 |
| **hold** | 暂不建议直接跑步 | 建议先做力量/快走/游泳，或就医评估后再来 |

**安全红线**（以下情况必须 hold，不可妥协）：
- 未控制的高血压（>160/100）
- 近期心绞痛/胸闷/不明原因晕厥
- 急性关节损伤未愈
- 妊娠期（需产科评估）
- 严重心律失常未评估

**怎么用**：

```bash
python3 scripts/screen.py \
  --age 35 --gender male --height 175 --weight 82 \
  --resting-hr 72 \
  --injuries "右膝:髌骨软化:已康复6个月:中" \
  --medical "无" \
  --running-exp none \
  --exercise-history "近1年每周2次力量训练" \
  --output runner-data.json
```

伤病格式：`部位:问题:状态:严重度`，多条用逗号分隔。
医疗史：如"高血压服药中,糖尿病"，无则填"无"。

### 阶段3：基线测试与分析（1 次测试 + 自动分析）

**要回答的问题**：你现在的真实跑步能力如何？心率区间和配速区间是多少？

**测试方式**（根据阶段2结论选）：

| 筛查结论 | 测试方式 | 目的 |
|---|---|---|
| pass 有跑步基础 | 20 分钟阈值跑 + 5K 测试 | 标定心率与配速区间 |
| pass 无基础 | 1 公里慢跑（能跑就跑，不能走跑） | 看心率反应与步频 |
| caution | 30 分钟走跑结合（走3跑1） | 观察心率恢复、关节反应 |

**测试中采集**：距离、时长、平均心率、最大心率、步频、RPE（主观劳累度1-10）、路面、主观感受。

**记录基线测试**：

```bash
python3 scripts/log_run.py --baseline \
  --date 2026-06-18 \
  --distance 1 --duration 8 --pace "8:00" \
  --hr 158 --max-hr 172 --cadence 164 --rpe 7 \
  --surface "操场塑胶" --note "1km慢跑测试" \
  --file runner-data.json
```

**自动分析**：

```bash
python3 scripts/analyze.py --baseline --file runner-data.json
```

分析输出：
- 心率区间标定（Z1-Z5，基于实测最大心率，用 Karvonen 储备心率法）
- 配速区间推算（以基线配速为 Z3 锚点）
- 步频评估（<160 严重偏低 / 160-170 偏低 / 170-185 理想）
- 有氧基础评估（Z2 心率下配速 >7:00 → 薄弱）
- 综合体能评级：low / moderate / good

### 阶段4：定制训练计划

**前置条件**：阶段1-3 必须全部完成，且阶段2 结论不是 hold。否则拒绝生成。

```bash
python3 scripts/gen_plan.py --profile --weekly-days 4 --output runner-data.json
```

`--profile` 会自动读取前三阶段数据，综合决策计划类型：

| 目标 + 筛查 + 体能 | 计划类型 | 周期 |
|---|---|---|
| 减重/BMI高/low | couch-to-5k 走跑结合 | 12-16 周 |
| 5K/pass/low | couch-to-5k | 8-12 周 |
| 5K/pass/moderate | 5k-race | 8 周 |
| 半马/pass/moderate+ | half-marathon | 12-16 周 |
| 半马/pass/low | 先 couch-to-5k 再衔接 | 20-24 周 |
| 全马/pass/good | marathon | 16-18 周 |
| 全马/low-moderate | **不建议直接上全马**，先半马 | — |

**自动约束适配**：
- 步频低 → 每周加 1 次步频专项
- 有氧薄弱 → E 跑占比提升到 80%+
- 伤病/筛查 caution → 加力量训练日，跑量递进限 8%（比标准 10% 更保守）
- BMI 高 → 走跑结合起步，不追求距离

---

## 日常使用：记录与自动回流

### 记录每次跑步

```bash
python3 scripts/log_run.py \
  --date 2026-06-18 --distance 5 --duration 28 --pace "5:36" \
  --hr 152 --cadence 172 --rpe 6 --note "晨跑轻松" \
  --file runner-data.json
```

**记录后自动回流检测**，发现异常会立即提示：

| 检测项 | 触发条件 | 建议 |
|---|---|---|
| 🔴 过度训练 | 连续3次RPE≥8且配速无提升 | 减量，回阶段3重评 |
| 🔴 急性疲劳 | 单次RPE≥9 | 休息2-3天降强度 |
| 🔴 跑量飙升 | 周跑量增幅超阈值 | 伤病风险，减量 |
| 🟡 配速退步 | 同心率下配速慢15秒+ | 有氧退步，回阶段3 |
| 🟡 疼痛记录 | note含"痛/疼/不适" | 回阶段2记录伤病 |
| 🟡 心率异常 | Z5心率但RPE低 | 心率漂移，留意耐力 |

### 定期复盘

```bash
# 近4周分析
python3 scripts/analyze.py --range 4w --file runner-data.json

# 月度汇总
python3 scripts/analyze.py --month 2026-06 --file runner-data.json

# 计划执行对照
python3 scripts/analyze.py --plan-progress --file runner-data.json
```

### 导出计划到手机日历

```bash
python3 scripts/export_ical.py --file runner-data.json --output training-plan.ics
```

生成的 .ics 文件导入方法：
- **iPhone**：邮件发送附件，点击导入
- **安卓**：导入 Google Calendar 或日历 App 打开
- **Outlook**：双击或拖入日历

每次训练含日期、时间、时长、训练内容、心率区间，提前 30 分钟提醒。

---

## 完整流程示例（从零开始）

```bash
# 1. 目标诊断
python3 scripts/motivate.py --output runner-data.json

# 2. 身体筛查
python3 scripts/screen.py --age 30 --gender female --height 162 --weight 55 \
  --resting-hr 62 --injuries "无" --medical "无" --running-exp casual \
  --output runner-data.json

# 3. 基线测试（先跑一次1公里记录数据）
python3 scripts/log_run.py --baseline --date 2026-06-18 --distance 1 --duration 6 \
  --pace "6:00" --hr 150 --max-hr 178 --cadence 172 --rpe 5 --file runner-data.json

# 4. 基线分析
python3 scripts/analyze.py --baseline --file runner-data.json

# 5. 生成定制计划
python3 scripts/gen_plan.py --profile --weekly-days 4 --output runner-data.json

# 6. 导出日历
python3 scripts/export_ical.py --file runner-data.json --output training-plan.ics

# 7. 日常记录（每次跑完）
python3 scripts/log_run.py --date 2026-06-20 --distance 5 --duration 28 \
  --pace "5:36" --hr 152 --cadence 172 --rpe 6 --note "晨跑" --file runner-data.json

# 8. 定期复盘
python3 scripts/analyze.py --range 4w --file runner-data.json
```

---

## 常见问题

**Q：我没有心率表/运动手表，能用吗？**
A：能。心率是推荐项但非必须。基线测试至少需要距离+时长+RPE，系统会自动推算配速。有心率数据的话分析会更精确。

**Q：阶段2筛查结果是 caution 怎么办？**
A：caution 意味着可以跑但有约束。系统会给出具体限制（如限频3次/周、避开下坡、加力量训练），按约束执行即可。如果约束涉及伤病，建议先咨询医生。

**Q：阶段2结果是 hold 怎么办？**
A：hold 表示暂不建议直接开始跑步。先按建议做替代运动（快走/游泳/力量训练），或就医评估，条件满足后再来。

**Q：计划生成后能改吗？**
A：能。每次记录跑步后系统会自动检测异常，若触发回流条件（如连续高RPE、配速退步），会提示你回到阶段3重评，重新生成计划。

**Q：我可以跳过某个阶段吗？**
A：不能。阶段4 有前置条件检查，缺任何一阶段都会拒绝生成计划。这是为了确保方案基于你的真实情况，而非拍脑袋。

**Q：支持英里吗？**
A：当前版本统一用公里。1 英里 ≈ 1.609 公里，可自行换算输入。

**Q：数据存在哪？安全吗？**
A：全部存在本地 `runner-data.json`，不上传任何服务器。你的健康数据只属于你。

---

## 脚本速查表

| 脚本 | 用途 | 关键参数 |
|---|---|---|
| `motivate.py` | 阶段1 目标诊断 | `--goal` `--success` `--timeframe` |
| `screen.py` | 阶段2 身体筛查 | `--age` `--height` `--weight` `--injuries` `--medical` |
| `log_run.py` | 记录跑步/基线测试 | `--distance` `--hr` `--cadence` `--rpe` `--baseline` |
| `analyze.py` | 分析（基线/周/月/计划） | `--baseline` `--range 4w` `--month` `--plan-progress` |
| `gen_plan.py` | 阶段4 生成计划 | `--profile` `--weekly-days` `--plan-type` |
| `export_ical.py` | 导出日历 | `--start-date` `--output` |

---

## 安全声明

- 本工具提供跑步训练建议，**不替代专业医疗诊断**
- 阶段2 筛查的安全红线基于常见运动医学共识，但无法覆盖所有个体情况
- 如有慢性病、心血管问题、近期手术史，**务必在开始任何运动计划前咨询医生**
- 训练中如出现胸痛、头晕、呼吸困难等异常，**立即停止并就医**
