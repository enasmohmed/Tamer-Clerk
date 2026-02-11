# خطوات إنشاء كارد Warehouse (من الأدمن حتى الظهور في التاب)

الكارد يظهر **ديناميك** في تاب **Warehouse**: بمجرد إكمال البيانات من الأدمن يظهر الكارد تلقائياً في الواجهة.

---

## ما هو Display order؟

**Display order** = رقم للترتيب (0، 1، 2، 3...).

- **الأصغر يظهر أولاً.** مثلاً: لو عندك 3 مستودعات ووضعتِ لـ Jeddah = 1، Riyadh = 2، Dammam = 3، هتظهر بالترتيب: Jeddah ثم Riyadh ثم Dammam.
- في **Status / Business Unit / Activity / Warehouse** نفس الفكرة: الرقم يتحكم في ترتيب الظهور في القوائم أو في الصفحة.
- ممكن تتركيه **0** لكل الحاجات؛ الترتيب يبقى حسب الاسم أو حسب الإضافة.

---

## الترتيب في الأدمن

في لوحة الأدمن، النماذج مرتبة من **1 إلى 8** بالترتيب اللي تمشي فيه الخطوات:

| # | النموذج في الأدمن | ماذا تفعلين |
|---|-------------------|-------------|
| 1 | **1. Statuses (الحالات)** | تضيفين الحالات + الألوان |
| 2 | **2. Business Units** | تضيفين Pharma, FMCG, Retail |
| 3 | **3. Business Systems** | تضيفين LogFire, SAP, WMS-X... |
| 4 | **4. Activities** | تضيفين Inbound, Outbound... |
| 5 | **5. Warehouses** | تضيفين المستودع (مثلاً Jeddah Warehouse) |
| 6 | **6. Warehouse Business Systems** | تربطين المستودع بـ Business + System |
| 7 | **7. Warehouse Employee Summaries** | تضيفين ملخص الموظفين للمستودع |
| 8 | **8. Warehouse Phase Statuses** | تضيفين صفوف Phase Status |

امشي بالترتيب من 1 → 8 عشان تنشئي كارد واحد كامل.

---

## مثال كامل: إنشاء كارد واحد باسم "Jeddah Warehouse"

اتبعي الخطوات بالترتيب واكتبي القيم كما هي (أو غيّري الأسماء حسب بياناتك).

### الخطوة 1: Statuses

- ادخلي **1. Statuses (الحالات)** → Add Status.
- أضيفي سجلين:
  - **Name:** Active | **Color hex:** `#2e7d32` | **Is warehouse status:** ✓ | **Is phase status:** ☐ | **Display order:** 0
  - **Name:** Completed | **Color hex:** `#2e7d32` | **Is warehouse status:** ☐ | **Is phase status:** ✓ | **Display order:** 0
- (اختياري) أضيفي: Partial، Pending، In Progress، Not Started مع ألوان مناسبة وعلّمي **Is phase status** لللي هتستخدميهم في Phase Status.

### الخطوة 2: Business Units

- ادخلي **2. Business Units** → Add Business Unit.
- أضيفي ثلاث سجلات: **Pharma** (Display order: 0)، **FMCG** (1)، **Retail** (2).

### الخطوة 3: Business Systems

- ادخلي **3. Business Systems** → Add Business System.
- أضيفي أنظمة مثل: **LogFire** (ربطيها بـ Pharma)، **SAP** (FMCG)، **WMS-X** (Retail). **Display order** يمكن 0 لكلهم.

### الخطوة 4: Activities

- ادخلي **4. Activities** → Add Activity.
- أضيفي: **Inbound**، **Outbound**، **Pending**، **Not Started**. **Display order** يمكن 0.

### الخطوة 5: Warehouse (المستودع)

- ادخلي **5. Warehouses** → Add Warehouse.
- **Name:** Jeddah Warehouse  
- **Status:** اختاري **Active** (اللي أنشأتيها في الخطوة 1).  
- **Display order:** 1 (لو عندك مستودعات ثانية، 1 = يظهر أولاً).

احفظي. من هنا يبقى عندك مستودع جاهز؛ الكارد هيظهر بعد ما تكملي الخطوتين 6 و 7 (واختياري 8).

### الخطوة 6: Warehouse Business Systems (جدول Business | System داخل الكارد)

- ادخلي **6. Warehouse Business Systems** → Add.
- أضيفي **3 صفوف** (واحد لكل وحدة أعمال):
  - Warehouse: **Jeddah Warehouse** | Business unit: **Pharma** | System: **LogFire**
  - Warehouse: **Jeddah Warehouse** | Business unit: **FMCG** | System: **SAP**
  - Warehouse: **Jeddah Warehouse** | Business unit: **Retail** | System: **WMS-X**
- احفظي كل سجل.

### الخطوة 7: Warehouse Employee Summaries (ملخص الموظفين)

- ادخلي **7. Warehouse Employee Summaries** → Add.
- **Warehouse:** Jeddah Warehouse (واحد فقط لكل مستودع).
- **Allocated count:** 32  
- **Pending or edit count:** 13 (رقم القلم، أو 0 لو مش محتاجاه).  
- **Phase label:** Phase 1  
- **Phase status label:** Completed  

احفظي.

### الخطوة 8: Warehouse Phase Statuses (جدول Phase Status داخل الكارد)

- ادخلي **8. Warehouse Phase Statuses** → Add.
- أضيفي عدة صفوف، مثلاً:
  - Jeddah Warehouse | Pharma | Inbound | Status: **Completed**
  - Jeddah Warehouse | FMCG | Inbound | Status: **Pending**
  - Jeddah Warehouse | Retail | Outbound | Status: **Completed**
- **Start date** و **End date** اختياري (مثلاً 01-Feb، 02-Feb).

---

## بعد الإكمال

ارجعي لصفحة الداشبورد وافتحي تاب **Warehouse**. يفترض يظهر كارد **Jeddah Warehouse** مع:

- شارة **Active** بلون أخضر
- جدول Business | System (Pharma–LogFire، FMCG–SAP، Retail–WMS-X)
- Employees Summary (32 Allocated، 13، Phase 1، Completed)
- جدول Phase Status بالصفوف اللي أضفتيها

لو الكارد مش ظاهر، حدّثي الصفحة (F5) وتأكدي أن كل الخطوات من 5 إلى 8 مضافة لنفس المستودع **Jeddah Warehouse**.

---

## ملخص سريع (ترتيب التنفيذ)

| # | ماذا تفعل | أين في الأدمن |
|---|-----------|----------------|
| 1 | إضافة الحالات (Active, Partial, Completed, Pending, …) مع الألوان | 1. Statuses |
| 2 | إضافة وحدات الأعمال (Pharma, FMCG, Retail) | 2. Business Units |
| 3 | إضافة الأنظمة (LogFire, SAP, WMS-X, …) | 3. Business Systems |
| 4 | إضافة النشاطات (Inbound, Outbound, …) | 4. Activities |
| 5 | إنشاء المستودع واختيار حالته (مثلاً Jeddah Warehouse + Active) | 5. Warehouses |
| 6 | ربط المستودع بوحدات أعمال + أنظمة (صف لكل Business + System) | 6. Warehouse Business Systems |
| 7 | إضافة ملخص الموظفين للمستودع (واحد لكل مستودع) | 7. Warehouse Employee Summaries |
| 8 | إضافة صفوف Phase Status (Business + Activity + Status + تواريخ) | 8. Warehouse Phase Statuses |

بعد إكمال 5 → 6 → 7 → 8 **لكل مستودع**، كارد المستودع يظهر في تاب **Warehouse** ويكون **Responsive**.
