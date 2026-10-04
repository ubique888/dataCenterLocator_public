# 电力与网络连接：三指标接入与可视化设计

状态：用户已要求实施。此设计约束接入与展示范围，实施状态记录在对应 implementation plan 中。

## 1. 目标与用户流程

支持面向单站 100 MW 及以下推理数据中心的早期场址比较。用户先看地图位置，再用三个原始指标筛选，打开详情检查关联机房与来源，最后通过双轴气泡图比较电力设施接近度与网络互联接近度之间的取舍。

本轮建立地理筛选指标，不推导可用 MW、通电月份、真实网络时延、可购买带宽或线路冗余；不创建综合评分。100 MW 是业务研究范围，不是这三项数据能够认证的能力上限。

### 三项指标

| 显示名称 | 发布字段 | 单位/方向 | 计算方式 |
|---|---|---|---|
| 变电站距离 | `substation_distance_km` | km，较小表示距离较近 | EPA 原有 `substation_distance`（英里）× 1.609344 |
| 互联机房距离 | `peering_facility_distance_km` | km，较小表示距离较近 | 到最近合格美国 PeeringDB 实体机房的 WGS84 椭球测地距离 |
| 该机房网络数 | `peering_facility_network_count` | 个，较大表示登记网络较多 | 读取上项同一机房的 `net_count` |

合格机房定义：`country == "US"`、`status == "ok"`、有效经纬度、非负整数 `ix_count >= 1`。机房有互联网交换点（IXP）入驻；这不是所有光纤节点、运营商 PoP 或可接入机房的完整清单。

第三项必须绑定第二项选出的机房。不得选择最近机房的距离，却使用更远大型机房的网络数；也不因最近机房的网络数缺失而改选更远机房。

## 2. 当前项目边界

代码和产物均在 `infrastructure-inheritance-symbiosis/` 子目录中。

- 当前 `data/processed/site_features.parquet` 有 8,479 行，每个 EPA `site_id` 一行。
- `substation_distance` 来源单位是英里，现有发布记录该字段完整；原始 EPA 数据为 2022 版（2023 更新），筛选依据包含 2021 年场址快照。
- 这 8,479 行已经经过面积 ≥50 acres、输电电压 ≥115 kV、输电距离 ≤3 mi、变电站距离 ≤5 mi 的旧筛选。
- 更完整的 190,976 条 EPA 记录存在于上游表，但单纯降低页面输入框的面积阈值，不能恢复早已被过滤掉的场址。

**第一轮范围：给既有 8,479 条记录补充三指标。** 页面对这一候选范围作常驻说明：`Existing EPA screened candidates · ≥50-acre source cohort`。新视图不再额外以旧分数、旧电厂身份过滤它们。扩大到小面积建筑、城市/近郊工业物业，是后续候选库调整，不混入本轮数据接入。

## 3. 数据源与更新方式

### 3.1 EPA

复用 `site_features.parquet`。保留原英里字段，新建 km 字段。变电站电压目前单位存疑，不参与此次指标。原数据不提供对应变电站的可靠资产 ID/坐标，因而不能据距离在地图上猜测位置。

### 3.2 PeeringDB

使用正式公开 `fac` API 的 JSON 数据；实施时先做小样本访问检查，再取得完整美国机房快照。接口只在构建时访问，浏览页面不请求 PeeringDB。

需要的字段：

```text
id, name, country, state, city, latitude, longitude,
status, ix_count, net_count, updated
```

保存原始响应、请求参数、获取开始/结束时间、每页记录数、响应哈希和清洗统计。`updated` 是来源记录更新时间；`retrieved_at` 是本项目获取时间，两者分别保留。没有更新时间则显示 Unknown。

初版由显式构建命令获取快照；已有快照时可以完全本地重算。暂不创建定时任务。未来若增加周期更新，可在用户指定频率后配置。

### 3.3 清洗规则

1. `id` 为唯一正整数。完全相同的重复行去重并计数；相同 ID 内容冲突时停止发布该快照并记录冲突，不能静默挑选。
2. 坐标必须为有限数字，在全球经纬度范围内，且不是 `(0,0)`；缺失、非法记录隔离到拒绝记录表。保留来源国家字段；不用随意大陆包围盒排除 AK/HI。
3. `ix_count` 缺失/非法时不能确认合格；有效且为 0 时明确排除。
4. `net_count` 缺失/负数/非整数时记 null 并记录原因，不删除本来合格的机房；有效 0 原样保留。
5. `status` 非 `ok` 不参与空间匹配。
6. 不把名称相同或坐标相同的不同 ID 擅自合并。同一园区可有多个合法记录。
7. 数据库未收录不等于没有互联条件。网页始终把对象称作“最近登记机房”。

### 3.4 访问与失败处理

普通公开查询可不登录；需要更高额度时可使用用户自行配置的只读 API key。HTTP 429 按 Retry-After 处理；有上限地重试网络/5xx 错误。401/403、非 JSON、字段结构变化、分页失败、内容冲突都不得用空表替代成功快照。

完整获取并清洗后才生成新版本。失败保留既有可用快照及页面；首次没有快照时报告缺少数据。真实但无合格机房的完整快照可以生成明确的 `no_eligible_facilities` 状态。

## 4. 数据结构与空间匹配

### 4.1 产物

```text
data/raw/peeringdb/<UTC快照时间>/fac_page_*.json
data/raw/peeringdb/<UTC快照时间>/manifest.json
data/processed/peering_facilities.parquet
data/processed/site_connectivity_features.parquet
outputs/validation/peeringdb_rejected_records.csv
outputs/validation/power_connectivity_summary.json
outputs/power_connectivity_preview.html
```

`site_connectivity_features.parquet` 是按 `site_id` 关联的独立补充表；原始 `site_features.parquet` 仍作为基础特征输入。这样旧流程重建时不会意外丢失新数据，新接入也不会改写原分数。

### 4.2 补充表字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `site_id` | int64 | 与当前基础表一对一 |
| `substation_distance_km` | nullable float64 | 原英里距离换算；无效值为 null |
| `peering_facility_id` | nullable Int64 | 选中的 PeeringDB 机房 ID |
| `peering_facility_distance_km` | nullable float64 | 未四舍五入的 WGS84 距离 |
| `peering_facility_network_count` | nullable Int64 | 来自同一选中机房 |
| `connectivity_status` | string | `matched` / `invalid_site_coordinates` / `no_eligible_facilities` |
| `peering_snapshot_id` | string | 快照目录名，与 manifest 对应 |

机房名称、地点、坐标、计数更新时间和 PeeringDB 页面 URL 放在单独的机房维表中，通过 ID 关联；不在数千条站点 JSON 中重复存储。

### 4.3 距离算法

先按机房 ID 升序排列，使用现有依赖 `pyproj.Geod(ellps="WGS84").inv`，分块计算场址与所有合格机房的距离，取最小值。初始分块 128 个场址 × 512 个机房；无须引入新空间库。

不沿用现有 `nearest_within_km` 的固定 2/5 km 截断；否则远离互联枢纽的候选会全部丢失距离。相同数值距离按较小 ID 稳定选择，排序和筛选使用未舍入值。跨日期变更后最近机房可能改变，快照 ID 必须随结果保存。

## 5. 可视化

### 5.1 主布局：沿用地图和右侧详情

新增 `Power & connectivity` 视图。携带新数据的预览页默认进入该视图；`Inheritance & symbiosis` 作为另一视图保留原有行为。没有新数据的既有构建调用仍进入旧视图。

```text
┌ Power & connectivity  | Inheritance & symbiosis ───────────────────┐
│ 8,479 existing EPA candidates · source cohort ≥50 acres            │
├ 三项筛选 ─────────┬ 地图 / 对比图 / 表格 ────────────┬ 场址详情 ───┤
│ 变电站距离 ≤ __km │                                │ 三个原始值  │
│ 机房距离   ≤ __km │ 场址点 + 可选机房点             │ 来源与日期  │
│ 机房网络数 ≥ __  │                                │ 最近机房    │
│                  │ 或：双轴气泡图                 │ 关联含义    │
│ 匹配数 / 缺失数  │                                │ 原有资料    │
└──────────────────┴────────────────────────────────┴────────────┘
```

维持现有 IBM Plex 字体、纸白背景、深蓝文字；蓝绿色为普通候选，铜色只突出选中场址。新指标不使用原有 High on both axes 颜色来暗示合格。

### 5.2 三个筛选器

```text
Maximum substation distance · km
Maximum interconnection facility distance · km
Minimum networks at that facility
```

- 三项默认留空，含义是不限；无需预设业务合格阈值。
- 距离接受非负小数，网络数接受非负整数。非法输入显示字段错误，并保留上次有效结果，不把空字符串变成 0。
- 用户启用某项阈值后，该项缺失的候选不满足条件。未启用该阈值时，该项缺失不阻挡候选。
- Reset 只清空当前视图的筛选状态。两个视图各有独立状态，旧分数和面积筛选不会隐形作用于新视图。
- 页面显示符合条件的场址数、当前结果中指标缺失的场址数。采用原始数值判断阈值，比较为包含边界的 ≤ / ≥。

### 5.3 地图

- 候选用相同大小的圆点，默认按“互联机房距离”着色；可切换为变电站距离或机房网络数。一次只映射一种指标，图例显示名称、单位和“登记/来源距离”。
- 两个距离模式使用统一固定分段：0–0.5、0.5–2、2–5、5–10、10–25、25–50、>50 km；分段仅供着色，不代表接入质量等级。零值属于第一段，边界使用右闭区间。
- 网络数着色分段：0、1–9、10–49、50–99、100–249、≥250；不把网络数称为带宽或物理运营商数量。
- 缺失值灰色描边，图例单列 Unknown；地图依然可点击。
- `Show matched interconnection facilities` 开关默认关闭；打开时只显示当前结果关联到的唯一机房，以不同形状标记并显示名称。
- 选中场址后可显示其对应机房，以虚线连接。固定标注 `Geographic association only — not a fiber route`；虚线不声称真实网络、光缆或连接权利。跨日期变更线要正确换经处理，不能横穿整张世界地图。
- 使用当前 USGS 底图及归属说明，不恢复标准 OSM 瓦片。机房快照随 HTML 嵌入；底图/Leaflet 加载仍需网络，不能把它称为完全离线地图。
- 变电站距离只作数值展示。原 HIFLD 图层若显示，继续说明它是独立来源，不能自动当作 EPA 对应的最近资产。

### 5.4 对比图：双轴气泡图

```text
机房距离 km
  ↑
  │        ○
  │   ○                  ○
  │      ◉
  │ ○
  └──────────────────────────→ 变电站距离 km
    左下：两种设施在地理上都较近
    气泡较大：同一机房登记网络较多
```

- X：变电站距离；Y：互联机房距离；气泡面积随同一机房网络数增加。
- 距离轴使用 `log1p(distance_km)`，刻度标签仍用 km，保留零值，并显式显示 `log(1 + km) scale`。轴域固定为完整候选集合的范围，筛选时不跳变；每轴上限至少为 1 km，确保全零/无值时坐标仍可呈现。
- 气泡大小固定取完整集合中已知网络数的 P95 为显示上限：`cap=max(1,P95)`，`radius=sqrt(16 + 128*min(count,cap)/cap)`。图例说明显示上限，tooltip 和表格仍显示真实计数，避免极端值遮挡其他点。
- 网络数为 null 时用固定半径的灰色空心圆；网络数确实为 0 时用最小实心圆。X/Y 缺失的记录不画在零点，显示“有 N 条结果缺少坐标轴指标，可在表格查看”。
- 鼠标悬停显示站点名、三个数值和最近机房名；点击打开同一个右侧详情，切换地图保留选择。避免用“低延迟”“可接 100 MW”描述左下区域。
- 使用 Canvas 绘制散点、SVG/HTML 绘制轴和图例，不引入图表框架。表格提供键盘可用的等效访问。

### 5.5 表格与详情

表格列：场址、州、变电站 km、互联机房 km、机房网络数、最近机房。支持按三指标单列排序；默认机房距离升序，空值最后，相同值按 site_id。每页 50 行，分页只影响表格显示，不改变地图、图表或结果总数。

详情最上方放三张数值卡；下面放最近机房名、城市、PeeringDB 链接、来源更新时间、快照时间。固定短说明：

> Distances indicate geographic proximity. Power availability and network performance require confirmation.

原 inheritance/symbiosis、热利用和周边设施作为折叠的背景资料保留；供电 MW、接电时间、RTT 不伪造数值。数值在显示时保留两位小数；非零但小于 0.01 km 的距离显示 `<0.01 km`。

### 5.6 窄屏和不可用状态

小屏按“筛选 → 当前视图 → 可收起详情”纵向排列，避免三列挤压。按钮、筛选和表格支持键盘操作。底图不可用时显示说明，但已内嵌的表格和对比图仍可使用；该退化不依赖 Leaflet 初始化成功。

## 6. 验收标准

1. 三项指标可追溯，第二/三项引用同一机房 ID。
2. 新表与输入场址 ID、行数一一对应，基础分数原样保留。
3. 合格机房过滤、计数缺失和 0、重复冲突、非法坐标有明确结果。
4. 地图、对比图、表格使用相同筛选结果和选择状态；未知值不会变成零。
5. 对比图尺度与气泡图例在筛选时固定；不会把邻近关系画成已建光缆。
6. 页面标明旧候选集合范围及两种数据日期；不会被误读为完整的小场址库。
7. API 获取失败不能发布“全国没有机房”的假结果。

## 7. 官方参考

- [PeeringDB 字段定义](https://www.peeringdb.com/apidocs/)
- [PeeringDB REST API 参数与 JSON 格式](https://docs.peeringdb.com/api_specs/)
- [公开访问与认证说明](https://docs.peeringdb.com/howto/authenticate/)
- [DOE 容量地图及其限制](https://www.energy.gov/cmei/vehicles/us-atlas-electric-distribution-system-hosting-capacity-maps)
- 项目现有来源和单位定义：`README_DATA.md`。

以上接口信息已查阅文档；PeeringDB 本机访问、完整数据量和缺失比例需在后续实施的首步确认。
