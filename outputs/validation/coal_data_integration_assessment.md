# Coal mine 数据接入评估

检查日期：2026-10-03。范围：公开数据下载、字段与空间质量、与现有 8,479 个候选场址的关联、现有 Python → Parquet → HTML 流程兼容性。本次只在 `outputs/validation/coal_integration_probe/` 保存探测数据和诊断结果，未更新正式候选表、评分或页面。

## 1. 结论

**可以融入现有项目，优先做现有场址的煤矿属性补充和地图图层；不能直接把所有煤矿记录加入现有评分排名。**

- 数据传输和技术格式基本可行：MSHA 全量 ZIP、eAMLIS ArcGIS 查询、GeoMine GeoJSON 均已实际读取。
- 关联和含义需要适配：EPA 场址、MSHA 矿山、eAMLIS 问题区域、GeoMine 许可边界不是同一对象，也不是一对一关系。
- 最容易发挥作用的是 **eAMLIS 补充现有废弃煤矿场址的治理问题和状态**；MSHA 用于矿山身份、类型、运行状态补充；GeoMine 用于边界及复垦背景。
- 全国矿井水冷却能力无法由这几份数据直接计算，现阶段只能保留为待验证机会。

## 2. 数据源实测

| 数据源 | 本次实测 | 接入难度 | 适合在项目中的用途 |
|---|---|---|---|
| MSHA Mines | 完整 ZIP 下载成功；92,037 行、59 字段、矿山编号唯一；其中煤类记录 35,734 行 | 下载低；关联中 | 矿山类型、运行状态、独立点图层、身份佐证 |
| eAMLIS | Problems 图层计数 61,582；完整下载 PA/WV/VA Mapping 索引 8,937 行，编号唯一；已取得对应问题样本 | 中，现有候选最容易受益 | 历史煤矿问题区域、治理状态、风险标记 |
| GeoMine Surface Coalmine Boundary | 78,389 个边界要素；读取 1,000 条属性和 3 个完整 GeoJSON 几何 | 中 | 矿区边界、空间包含/相交证据 |
| GeoMine Bond Status / PostMiningLandUse | 分别 38,253 / 16,925 个要素；元数据、计数、各 100 条属性样本可读 | 中 | 保证金/复垦阶段、采后土地用途信息 |
| Sierra Club Beyond Coal | 页面可通过网页阅读工具读取；本机普通 HTTP 请求返回 403；未确认可稳定下载的批量数据接口 | 不适合作为本轮主数据源 | 煤电厂退役状态的辅助证据 |

上述要素数都不是可建设场址数或唯一矿山数。边界、状态图层只做接口和样本审查，尚未下载全国全部几何、建立全国关联，亦未验证浏览器跨域实时加载。

### 来源和获取入口

- [MSHA 官方开放数据入口](https://arlweb.msha.gov/OpenGovernmentData/OGIMSHA.asp)、[Mines.zip](https://arlweb.msha.gov/OpenGovernmentData/DataSets/Mines.zip)、[字段定义](https://arlweb.msha.gov/OpenGovernmentData/DataSets/Mines_Definition_File.txt)。本次 ZIP 的 HTTP Last-Modified 为 **2026-10-02 11:09:30 GMT**，大小 7,306,254 bytes。SHA256：`c74533dd6aa42bf385e725af4a92501eb622a236f6819eaaea80a70417deae09`。服务端文件时间不代表每条历史记录均在该日更新。
- [eAMLIS 官方说明](https://www.osmre.gov/programs/e-amlis)、[公开地图服务](https://eamlis.osmre.gov/arcgis/rest/services/ProblemsStatus/MapServer)。官方将其定义为废弃矿地问题清单，包含待治理及已治理问题，覆盖也有限制，不能当作完整矿山或土地权属名录。
- [GeoMine 边界](https://geodata.osmre.gov/arcgis/rest/services/GeoMine/AllCoalmineOperations/MapServer/0)、[保证金状态](https://geodata.osmre.gov/arcgis/rest/services/GeoMine/ReclamationBondStatus/MapServer/0)、[采后土地用途](https://geodata.osmre.gov/arcgis/rest/services/GeoMine/PostMiningLandUse/MapServer/0)。边界包含露天采矿范围和地下采矿造成的地表扰动，不是完整地下巷道图。
- [Sierra Club 地图说明](https://www.sierraclub.org/coal/coal-plant-map)明确描述的是煤电厂及其退役计划，不能用作煤矿名录。

访问排查发现：旧 `geoservices.osmre.gov` 域名在本机解析失败；新 `geodata.osmre.gov` 可用。本环境 Python requests 的证书链校验失败，但系统 curl 使用默认 TLS 验证成功。正式采集需使用正常可信证书配置，无需关闭证书验证。已测试的政府接口无需账号或 API key；本次成功不构成长期可用性保证，应保存快照、来源和抓取日期。

## 3. 与现有候选的实际关联

现有发布表有 8,479 行，其中 4,079 行带废弃矿地来源标记，明确属于 PA/WV/VA 煤矿项目的有 3,626 行。这是 EPA 候选记录数，不能视为独立矿山数。

### eAMLIS：有可用编号桥梁，但需要质量分级

只对已识别命名空间做规范化：例如 `PA 5042 → PA005042`，`WV001352` 保持原值。没有把来源不明的 VA 数字编号强行转换为 AMLIS_KEY。

| 州 | 现有煤矿项目记录 | 编号关联上 eAMLIS | 编号关联且点位相距 ≤1 km |
|---|---:|---:|---:|
| PA | 2,289 | 1,254 | 1,214 |
| WV | 1,229 | 914 | 833 |
| VA | 108 | 0 | 0 |
| 合计 | **3,626** | **2,168（59.8%）** | **2,047（56.5%）** |

“编号关联”仍不是已完成全部身份验证：

- 2,168 条候选对应 **2,145 个** eAMLIS 区域编号，已有多个候选指向同一区域的情况。
- 其中 1,923 条名称在去除大小写和标点后相同；其余仍需检查名称差异。
- 10 条关联记录的 eAMLIS 坐标为 `(0,0)`；另有 111 条坐标落在本次美国粗略范围内、但与候选相距超过 1 km，最大约 84.6 km。它们需要核查，不能覆盖原候选坐标。
- ≤1 km 只是诊断阈值，区域代表点不同也可能产生距离差异；没有将其自动标记为已核实同一可用地块。表中距离用于粗筛，未作测绘精度验证。
- 一个区域有多个治理问题：样本 `WV000239` 对应 5 条问题，同时出现已完成和待治理；`PA005042` 同时有治理中及已完成状态。不能取第一条状态就宣称整个矿区已经完成复垦。

建议以 `site_id ↔ AMLIS_KEY` 单独关联表保存关系，问题明细另表保存；汇总出未完成问题数、问题类型和证据日期。无法关联应显示 unknown，而不是“没有风险”。

### MSHA：易下载，难以直接合并

- 现有 EPA `source_site_id` 与 MSHA 煤类 `MINE_ID` 的原始字符串精确相等数为 **0**。这说明没有可直接使用的同名主键，不表示场址没有对应矿山。
- 35,734 条煤类记录包括 Surface 17,623、Underground 14,589、Facility 3,413、类型缺失 109。Facility 不能全部当成矿坑；记录也包含大量历史停用矿山。
- 11,727 条缺少至少一个坐标；63 条有坐标但超出全球经纬度范围；另有 602 条虽落在全球范围内，却不符合本次美国粗略范围筛选。例如存在 `0.1694, -1.0169` 等占位式值。
- 只有 **23,342 条（65.3%）** 通过本次粗略空间范围检查（纬度 17–72、经度 -180 至 -60）。这不是逐州或实地坐标准确性认证。
- 现有明确煤矿项目记录中，2,646 条在 2 km 内能找到 MSHA 煤类记录，包含附属设施；这里只保存为 `proximity_only_not_verified_identity`。不能把邻近矿山的状态、矿种或资产直接归给候选场址。
- `MINE_ID` 必须按字符串读取并保留前导零。当前快照可用 Latin-1 无损解码后解析竖线分隔文本；UTF-8 和 CP1252 在本次文件均遇到非法字节。正式管道还需清理显示文本中的控制字符并监控编码变化。

### GeoMine：空间数据可用，主键覆盖不足

- 全国 78,389 条边界中仅 **10,719 条的 `msha_id` 非 NULL（13.7%）**，这仍可能包含占位或不规范值，是有效连接率的上限。
- PA 36,729 条、WV 4,229 条、VA 574 条边界的 `msha_id` 全部为空。恰好这些州占现有明确煤矿项目记录的全部。
- `permit_id`、`national_id`、主管机构字段可以辅助关联，但必须明确州/机构命名空间；样本存在一个编号对应多个要素的情况。
- GeoJSON 的 Polygon/MultiPolygon 样本均可由现有 Shapely 解析，3 个样本几何有效；可用 `outSR=4326` 输出，避免把 Web Mercator 坐标直接放进 Leaflet。
- 仅 3 个未简化边界样本已有约 **367 KB**，不宜把全国全部精细多边形塞入当前单个 HTML。建议离线裁剪到候选附近、按缩放简化并建立索引，详情选择时加载相关几何。
- 不得把 Web Mercator `st_area(shape)` 当作可建设面积。许可范围、扰动面积、复垦用途面和实际可建设地块面积的含义不同。

## 4. 当前项目是否能承接

| 环节 | 已检查结果 | 必要改动 |
|---|---|---|
| `src/processing/site_features.py` | `build_site_features` 保留额外字段；实际内存试接入保留 8,479 行、唯一 EPA site_id 及全部原评分 | 增加矿山属性处理模块及来源字段即可；主键不替换 |
| `src/spatial/nearby.py` | 可复用点邻近检索；本次已用它做 MSHA 距离诊断 | 另加多边形相交/包含，以及关系证据类型 |
| `src/visualization/site_explorer.py` | 当前显式选择导出字段；试导出仍有 8,479 条记录，但新增矿山字段不会自动输出 | 增加字段映射、煤矿筛选器、详情证据和图例 |
| `src/processing/local_ecosystem.py` | 当前面向工业和污水点位 | 矿区面需新建独立图层/数据包 |
| `src/processing/repowering.py` | 初筛依赖面积、输电电压和距离等 EPA 字段 | 新 MSHA/eAMLIS 行缺这些条件，不能直接拼接为合格候选 |
| `src/processing/inheritance.py` | 电厂历史容量和电厂身份影响现有分数 | 煤矿潜力独立展示；新增煤矿评分时另行定义适用规则 |

内存试接入调用了真实的 `build_site_features` 和 `site_records`，仅在诊断目录写入结果。未重建正式 HTML，未宣称浏览器界面已完成验证。

### 评分限制

现有 inheritance 权重是历史电力资产 30%、输电 25%、变电站 20%、土地 15%、交通 10%，并乘以电厂身份系数。无可信电厂身份时，即便其他分项满分，最高为 `(25+20+15+10) × 0.7 = 49`。煤矿硬套这个模型会受到结构性影响。

推荐第一轮保留现有两项分数，新增可筛选的 `Coal mine reuse potential` 证据区。若之后需要煤矿专属分数，应明确其与电厂分数的适用范围和可比性。MSHA 的矿山状态、GeoMine 的保证金释放、eAMLIS 的某项治理完成，都不足以证明电力可接入、地基可用、地块可开发。

## 5. 推荐接入顺序和字段契约

1. **先接 eAMLIS**：补充现有煤矿来源记录；保存编号关联、名称一致性、坐标偏差、治理问题列表。已发现异常进入待核查状态。
2. **再接 MSHA**：建立独立矿山/设施点图层，增加类型和状态；与候选之间区分 exact-ID、人工核查、空间相交、附近记录等关系。
3. **再接 GeoMine**：增加候选附近边界、复垦阶段和土地用途；按多个要素聚合，保留原始明细和日期。
4. **煤矿新增候选及评分单独处理**：补面积、输电/变电距离、交通及用地证据，通过同等初筛后再进入候选集合。

建议保持 `site_id` 为现有 EPA 主键；外部标识分别为字符串 `msha_mine_id`、`amlis_key`、`geomine_national_id`，用单独关系表承接一对多。可发布字段包括：

- `mine_type_raw` / 标准化类型、`mine_status_raw` / 状态日期；类型代码必须按对应来源字典解释，不能跨库混用。
- `mine_relation_type`、`mine_match_evidence`、`mine_distance_km`、`mine_coordinate_review_required`。
- `aml_open_problem_count`、`aml_problem_types`、`reclamation_statuses`、`post_mining_land_uses`。
- `source_url`、`source_record_id`、`source_updated_at`、`retrieved_at`。

距离统一存为显式 `_km` 字段；现有 EPA 输电/铁路等距离仍有英里字段，需在界面标清单位。缺失值保留 null；不得用 0 表示未知。

## 6. 矿井水冷却目前的界限

本轮已检查的 MSHA/eAMLIS/GeoMine 数据没有足以推导持续冷却能力的水温、可持续流量、水质、抽水条件等成套字段。土地用途为水体、地下矿山身份、历史排水问题都不能替代这些数据。

[DOE Project Oasis 页面](https://www.energy.gov/nepa/articles/cx-031654-energy-delta-lab-project-oasis)描述的是以废弃地下矿井水用于数据中心冷却的可行性试验。本轮没有取得可批量接入的全国矿井水冷却资源实测清单。应显示“需要水文和工程验证”，不填充可用冷却 MW，也不直接增加 symbiosis 分数。

## 7. 审查证据与复现

同目录 `coal_integration_probe/` 保存了公开下载、原始 ArcGIS 响应、访问日志及以下汇总：

- `msha_profile.json`：全国记录、类型、坐标、邻近诊断、特征和导出流程试运行。
- `arcgis_profile.json`：三州索引关联、异常坐标、边界编号覆盖、样本几何及复垦状态。
- `eamlis_key_link_diagnostic.csv`：每条现有煤矿候选的编号、名称和距离诊断。
- `msha_proximity_diagnostic.csv`：仅表示邻近的 MSHA 记录，不能作为身份确认表。
- `arcgis_*_results.json`：实际请求 URL、记录数、响应大小及分页截断标识。

本地复现（项目子目录内）：

```sh
../.venv/bin/python outputs/validation/coal_integration_probe/profile_msha.py
../.venv/bin/python outputs/validation/coal_integration_probe/profile_arcgis.py
```

后续还需完成全国边界关联、来源字典规范化、数据更新任务及前端浏览器验证；这些不属于本次已完成的接入评估。
