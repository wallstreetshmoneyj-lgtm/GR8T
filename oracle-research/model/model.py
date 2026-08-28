"""ORCL independent model. All $ in millions unless noted.
Every historical input is tagged with its primary source."""
import json, math
from collections import OrderedDict

SRC = "FY2026 10-K, acc 0001193125-26-277521, filed 2026-06-22 (FYE 5/31/2026)"
PR  = "Q4/FY26 press release, Ex-99.1 to 8-K filed 2026-06-10, acc 0001193125-26-265848"

# ============================================================ HISTORICALS
H = OrderedDict()
H['fy']            = [2024, 2025, 2026]
# Income statement -- 10-K Consolidated Statements of Operations (R4)
H['rev_cloud']     = [19774, 24506, 33989]
H['rev_iaas']      = [ 6840, 10234, 18101]   # 10-K Note 14 revenue by offering (R89)
H['rev_saas']      = [12934, 14272, 15888]
H['rev_license']   = [ 5081,  5201,  4737]
H['rev_support']   = [19609, 19523, 19804]
H['rev_software']  = [24690, 24724, 24541]
H['rev_hardware']  = [ 3066,  2936,  3084]
H['rev_services']  = [ 5431,  5233,  5743]
H['rev_total']     = [52961, 57399, 67357]
H['cor_cloudsw']   = [ 9427, 11569, 17597]  # exclusive of intangible amortization
H['cor_hardware']  = [  891,   782,   868]
H['cor_services']  = [ 4825,  4576,  4556]
H['opex_sm']       = [ 8274,  8651,  8331]
H['opex_rd']       = [ 8915,  9860, 10272]
H['opex_ga']       = [ 1548,  1602,  1618]
H['amort_intang']  = [ 3010,  2307,  1671]
H['restructuring'] = [  718,   374,  1838]
H['op_income']     = [15353, 17678, 20606]
H['interest_exp']  = [ 3514,  3578,  4599]
H['nonop_net']     = [  -98,    60,  3547]
H['pretax']        = [11741, 14160, 19554]
H['tax']           = [ 1274,  1717,  2467]
H['net_income']    = [10467, 12443, 17087]
H['pref_div']      = [    0,     0,   103]
H['ni_common']     = [10467, 12443, 16984]
H['eps_diluted']   = [ 3.71,  4.34,  5.83]
H['waso_diluted']  = [ 2823,  2866,  2914]
H['waso_basic']    = [ 2744,  2789,  2860]
# Cash flow (R8)
H['ocf']           = [18673, 20821, 31977]
H['depreciation']  = [ 3129,  3867,  7623]
H['sbc']           = [ 3974,  4674,  4811]
H['capex']         = [ 6866, 21215, 55663]
H['unpaid_capex']  = [ 1637,  2970,  5279]
H['dividends_paid']= [ 4391,  4743,  5787]
H['buybacks']      = [ 1202,   600,    95]
# Balance sheet (R2) FY25/FY26 only
BS26 = dict(cash=31289, mkt_sec=605, ar=10385, prepaid=4288, ppe_net=99957,
            rou_op=29690, goodwill=62261, dta=11541, other_nca=11743, assets=261759,
            debt_cur=7199, ap=10977, accrued_comp=2225, defrev_cur=9916, other_cl=11447,
            debt_nc=122342, tax_payable=11771, lease_liab_nc=26648, other_ncl=16178,
            pref=4954, common_apic=43243, accum_deficit=-4309, aoci=-1380,
            equity_orcl=42508, nci=548, equity_total=43056)
BS25 = dict(cash=10786, ppe_net=43522, rou_op=13145, equity_orcl=20451, equity_total=20969,
            debt_cur=7271, debt_nc=85297, assets=168361)
# PP&E note (R49/R51)
PPE26 = dict(gross=122651, cip=39973, accum_dep=22694, net=99957,
             computer=59634, buildings=21263, ffe=452, land=1329, fin_lease_rou=7464)
PPE25 = dict(gross=59554, cip=16510, accum_dep=16032, net=43522, computer=30345,
             buildings=10881, ffe=466, land=1352, fin_lease_rou=2874)
# Debt maturities (R57) fiscal years
DEBT_MAT = {2027:7210, 2028:10145, 2029:5500, 2030:7250, 2031:9750, 'after':90250}
DEBT_TOTAL_PRINCIPAL = 130105
# Intangible amortization schedule (R53) -- disclosed, no estimate needed
AMORT_SCHED = {2027:731, 2028:694, 2029:620, 2030:582, 2031:377}
# RPO (10-K Note 1 + MD&A)
RPO26, RPO25 = 638000, 137800
RPO_SCHED = dict(m0_12=0.12, m13_36=0.34, m37_60=0.34, thereafter=0.20)
RPO_HIST = {'2024-05':97900,'2024-08':99100,'2024-11':97300,'2025-02':130200,
            '2025-05':137800,'2025-08':455300,'2025-11':523300,'2026-02':552600,'2026-05':638000}
# Non-GAAP bridge (press release)
NONGAAP26 = dict(opex_adj=-8320, sbc=4811, amort=1671, restr=1838, op_inc=28926,
                 tax=5537, tax_adj=3070, ni=22337, ni_common=22234, eps=7.63,
                 eps_ex_gains=6.83, gaap_tax_rate=0.126, nongaap_tax_rate=0.199)
NETCAPEX26 = dict(capex=-55663, st_fin=3345, cust_prepay=4592, net_outlay=-47726)
INVEST_GAIN26 = 2811   # non-operating: gains on marketable/non-marketable investments (Ampere, Bloom warrants)
# Guidance (press release, primary source)
GUID = dict(fy27_rev=90000, fy27_eps_ng=8.05, q1_eps_lo=1.72, q1_eps_hi=1.76,
            q1_rev_g_lo=.27, q1_rev_g_hi=.29, fy27_raise=40000, atm=20000,
            prepaid_or_cust_gpu=75000)
# Market data, Aug 27 2026 close
MKT = dict(price=151.94, date='2026-08-27', sh_out=2880.471, mcap=437660.0,
           rf=0.04672, beta=1.72, high52=345.72, low52_intraday=114.50,
           pt_avg=244.12, pt_lo=110.0, pt_hi=400.0, n_analysts=44)
# Preferred: 6.50% Series D mandatory convertible (10-K Note 10 / R70)
PREF = dict(shares=50000, liq_pref=100000, face=5000, rate=0.065, div_annual=325,
            min_ratio=499.8126, max_ratio=624.7657)
PREF['upper_conv_px'] = PREF['liq_pref']/PREF['min_ratio']   # ~$200.07
PREF['lower_conv_px'] = PREF['liq_pref']/PREF['max_ratio']   # ~$160.06
PREF['shares_if_conv_at_mkt'] = (PREF['max_ratio'] if MKT['price'] < PREF['lower_conv_px']
                                 else PREF['min_ratio']) * PREF['shares'] / 1e6  # millions

# ============================================================ DERIVED HISTORICALS
def gm(i):
    cor = H['cor_cloudsw'][i]+H['cor_hardware'][i]+H['cor_services'][i]
    return (H['rev_total'][i]-cor)/H['rev_total'][i]
H['gross_margin'] = [gm(i) for i in range(3)]
H['fcf'] = [H['ocf'][i]-H['capex'][i] for i in range(3)]
H['ebitda'] = [H['op_income'][i]+H['depreciation'][i]+H['amort_intang'][i] for i in range(3)]

# Decompose FY26 cost of revenue to derive an IaaS gross margin (ESTIMATE -- assumptions stated)
ASSUME_SUPPORT_GM = 0.93   # ANALYST ESTIMATE: software support gross margin
ASSUME_LICENSE_GM = 0.98   # ANALYST ESTIMATE
ASSUME_SAAS_GM    = 0.78   # ANALYST ESTIMATE
def derive_iaas_gm(i):
    sw_cost = H['rev_support'][i]*(1-ASSUME_SUPPORT_GM) + H['rev_license'][i]*(1-ASSUME_LICENSE_GM)
    cloud_cost = H['cor_cloudsw'][i] - sw_cost
    saas_cost = H['rev_saas'][i]*(1-ASSUME_SAAS_GM)
    iaas_cost = cloud_cost - saas_cost
    return 1 - iaas_cost/H['rev_iaas'][i], iaas_cost, cloud_cost
H['iaas_gm'] = [derive_iaas_gm(i)[0] for i in range(3)]
H['iaas_cost'] = [derive_iaas_gm(i)[1] for i in range(3)]
H['cloud_cost'] = [derive_iaas_gm(i)[2] for i in range(3)]
H['services_gm'] = [(H['rev_services'][i]-H['cor_services'][i])/H['rev_services'][i] for i in range(3)]
H['hardware_gm'] = [(H['rev_hardware'][i]-H['cor_hardware'][i])/H['rev_hardware'][i] for i in range(3)]

# ============================================================ SCENARIOS
FY = [2027, 2028, 2029, 2030, 2031]

BASE = dict(
    name='Base',
    # --- RPO decomposition. "Legacy" = pre-AI backlog still running off; "AI" = the FY26 step-change.
    rpo_legacy=140000,                       # ESTIMATE: ~FY25 RPO level, net of runoff/adds
    legacy_conv=[0.40,0.25,0.15,0.08,0.05],  # ESTIMATE: pre-AI backlog converts on ~2.5yr duration
    rpo_haircut=0.05,                        # % of AI backlog never recognised (counterparty default / renegotiation)
    ai_split_y23=[0.45,0.55],                # ESTIMATE: intra-bucket split of disclosed 34% (m13-36)
    ai_split_y45=[0.51,0.49],                # ESTIMATE: intra-bucket split of disclosed 34% (m37-60)
    # --- New bookings signed AFTER 5/31/2026 (pure estimate; dominates FY30-31)
    new_bookings=[100000, 80000, 70000, 65000, 60000],
    new_conv=[0.04,0.10,0.15,0.17,0.16],
    # --- Revenue not covered by RPO (hardware, non-committed consumption, some services/license)
    nonrpo_base=8500, nonrpo_growth=0.03,
    # --- Segment drivers for the non-IaaS lines (IaaS is the residual)
    saas_g=[0.12,0.11,0.10,0.09,0.08], lic_g=[-0.06]*5, sup_g=[-0.005]*5,
    svc_g=[0.08,0.07,0.06,0.05,0.05], hw_g=[0.05,0.05,0.04,0.04,0.04],
    # --- Margins
    iaas_nondep_cost=[0.375,0.360,0.345,0.330,0.320],  # % of IaaS revenue, ex-depreciation
    ocidep_share=[0.80,0.84,0.87,0.89,0.90],           # share of total depreciation charged to IaaS COGS
    saas_gm=[0.78,0.785,0.79,0.795,0.80], sup_gm=[0.93]*5, lic_gm=[0.98]*5,
    svc_gm=[0.21,0.215,0.22,0.22,0.22], hw_gm=[0.72]*5,
    # --- Opex
    sm_pct=[0.093,0.083,0.077,0.073,0.070],  # S&M as % of revenue (scale leverage)
    rd_growth=[0.08,0.08,0.07,0.06,0.06], ga_growth=[0.05]*5,
    sbc_growth=[0.06,0.06,0.05,0.05,0.05],
    restructuring=[600,400,300,300,300],
    # --- Capex / PP&E : LINKED, not a % of revenue.
    #     capex(t) funds the gross PP&E needed to serve IaaS revenue growth in (t+1),
    #     at asset_turn_full x utilization, plus maintenance replacement of retiring assets.
    asset_turn_full=0.50,      # ESTIMATE: IaaS revenue per $ gross PP&E at full utilisation
    utilization=[0.72,0.80,0.85,0.87,0.88],
    maint_capex_pct_dep=[0.30,0.35,0.40,0.45,0.50],
    iaas_g_terminal=0.06,      # IaaS growth assumed one year beyond the window, to size FY31 capex
    # Share of new capacity funded by customers (prepayments + customer-supplied GPUs).
    # Anchored to mgmt: "prepaid and customer supplied hardware portions ... now total $75 billion" (PR 6/10/26)
    cust_funded_capacity=[0.25,0.25,0.20,0.18,0.15],
    capex_floor_pct_prior=[0.0,0.35,0.35,0.35,0.35],
    # Committed spend floor: GPU/server orders and data-centre leases placed 12-18 months ahead
    # cannot be cancelled inside the year. This is what makes the bear case a funding problem.
    capex_min=[80000,30000,20000,14000,14000],
    impairment=[0,0,0,0,0],
    capex_equip=0.62, capex_bldg=0.30, capex_land=0.08,
    life_equip=6.0, life_bldg=25.0,
    cip_release=[0.70,0.30],       # opening CIP $39,973 placed in service FY27/FY28
    capex_inservice_split=[0.40,0.60],  # capex year t placed in service: 40% t, 60% t+1
    # --- Financing
    cost_new_debt=0.0675, rate_existing=0.0430, interest_income_rate=0.035,
    equity_raise=[20000, 0, 0, 0, 0], equity_price=[150.0,0,0,0,0],
    # --- Other
    tax_rate_gaap=[0.170,0.180,0.185,0.190,0.190], tax_rate_ng=[0.200]*5,
    dividend_ps=[2.00,2.00,2.04,2.12,2.20],
    dilution_sbc=0.010, pref_convert_fy=2029,
    nwc_pct_rev_change=0.02,   # incremental NWC as % of revenue change
    cust_prepay=[6000,4000,2000,1000,1000],  # customer prepayments in OCF
    st_fin_capex=[4000,3000,2000,1500,1500],
    wacc=0.100, terminal_growth=0.030,
)

BULL = dict(BASE, name='Bull',
    legacy_conv=[0.42,0.26,0.15,0.08,0.05],
    rpo_haircut=0.00, ai_split_y23=[0.48,0.52], ai_split_y45=[0.52,0.48],
    new_bookings=[160000,140000,120000,110000,100000], new_conv=[0.05,0.12,0.17,0.18,0.17],
    iaas_nondep_cost=[0.360,0.335,0.310,0.290,0.275],
    saas_g=[0.13,0.12,0.11,0.10,0.09],
    sm_pct=[0.090,0.079,0.072,0.068,0.065],
    asset_turn_full=0.55, utilization=[0.78,0.87,0.91,0.92,0.92],
    maint_capex_pct_dep=[0.30,0.35,0.40,0.45,0.50], iaas_g_terminal=0.10,
    cust_funded_capacity=[0.28,0.28,0.24,0.22,0.20], capex_floor_pct_prior=[0.0,0.35,0.35,0.35,0.35],
    capex_min=[88000,32000,22000,16000,16000],
    cost_new_debt=0.0600, tax_rate_gaap=[0.160,0.170,0.175,0.180,0.180],
    equity_raise=[20000,0,0,0,0], equity_price=[175.0,0,0,0,0],
    wacc=0.092, terminal_growth=0.035)

BEAR = dict(BASE, name='Bear',
    legacy_conv=[0.36,0.23,0.14,0.08,0.05],
    rpo_haircut=0.20,   # a large AI counterparty cannot fund its commitment / renegotiates
    ai_split_y23=[0.38,0.50], ai_split_y45=[0.45,0.42],   # plus slippage: build runs late
    new_bookings=[60000,40000,35000,30000,30000], new_conv=[0.03,0.08,0.12,0.14,0.14],
    iaas_nondep_cost=[0.400,0.395,0.385,0.375,0.370],
    ocidep_share=[0.82,0.86,0.89,0.91,0.92],
    saas_g=[0.10,0.08,0.07,0.06,0.05], svc_g=[0.05,0.04,0.03,0.03,0.03],
    sm_pct=[0.098,0.092,0.088,0.085,0.083],
    asset_turn_full=0.44, utilization=[0.66,0.66,0.64,0.62,0.60],
    maint_capex_pct_dep=[0.30,0.35,0.40,0.45,0.50], iaas_g_terminal=0.00,
    cust_funded_capacity=[0.22,0.20,0.15,0.12,0.10],
    capex_floor_pct_prior=[0.0,0.80,0.72,0.60,0.55],  # committed orders cannot be cancelled quickly
    capex_min=[78000,58000,34000,20000,16000],
    impairment=[0,12000,20000,10000,0],
    cost_new_debt=0.0775, rate_existing=0.0430,
    tax_rate_gaap=[0.185,0.195,0.200,0.205,0.205],
    equity_raise=[20000,15000,10000,0,0], equity_price=[120.0,100.0,95.0,0,0],
    wacc=0.112, terminal_growth=0.020)

# ============================================================ ENGINE
def run(S):
    n=5; o={}
    # ---------- RPO runoff from the 5/31/2026 snapshot (disclosed 12/34/34/20 schedule) ----------
    legacy=S['rpo_legacy']; ai=RPO26-legacy
    leg=[legacy*c for c in S['legacy_conv']]
    ty1,ty23,ty45 = RPO_SCHED['m0_12']*RPO26, RPO_SCHED['m13_36']*RPO26, RPO_SCHED['m37_60']*RPO26
    ai_y1, ai_y23, ai_y45 = ty1-leg[0], ty23-(leg[1]+leg[2]), ty45-(leg[3]+leg[4])
    hc=1-S['rpo_haircut']
    aiy=[ai_y1*hc, ai_y23*S['ai_split_y23'][0]*hc, ai_y23*S['ai_split_y23'][1]*hc,
         ai_y45*S['ai_split_y45'][0]*hc, ai_y45*S['ai_split_y45'][1]*hc]
    o['rpo_legacy_conv'], o['rpo_ai_conv'], o['ai_backlog'] = leg, aiy, ai
    o['rpo_runoff']=[leg[i]+aiy[i] for i in range(n)]
    # ---------- new bookings layer (pure estimate; dominates FY30-31) ----------
    newrev=[0.0]*n
    for i in range(n):
        for j in range(i+1):
            k=i-j
            if k<len(S['new_conv']): newrev[i]+=S['new_bookings'][j]*S['new_conv'][k]
    o['rev_new_bookings']=newrev
    o['rev_nonrpo']=[S['nonrpo_base']*(1+S['nonrpo_growth'])**(i+1) for i in range(n)]
    o['rev_total']=[o['rpo_runoff'][i]+newrev[i]+o['rev_nonrpo'][i] for i in range(n)]
    # ---------- segments (IaaS is the residual) ----------
    def grow(b,g):
        out=[];v=b
        for x in g: v*= (1+x); out.append(v)
        return out
    o['rev_saas']=grow(H['rev_saas'][2],S['saas_g']);      o['rev_license']=grow(H['rev_license'][2],S['lic_g'])
    o['rev_support']=grow(H['rev_support'][2],S['sup_g']); o['rev_services']=grow(H['rev_services'][2],S['svc_g'])
    o['rev_hardware']=grow(H['rev_hardware'][2],S['hw_g'])
    o['rev_iaas']=[o['rev_total'][i]-(o['rev_saas'][i]+o['rev_license'][i]+o['rev_support'][i]
                   +o['rev_services'][i]+o['rev_hardware'][i]) for i in range(n)]
    o['rev_cloud']=[o['rev_iaas'][i]+o['rev_saas'][i] for i in range(n)]
    o['rev_software']=[o['rev_license'][i]+o['rev_support'][i] for i in range(n)]
    o['iaas_growth']=[o['rev_iaas'][i]/(H['rev_iaas'][2] if i==0 else o['rev_iaas'][i-1])-1 for i in range(n)]
    # ---------- LINKED capex: growth capacity + maintenance ----------
    # capex(t) buys the gross PP&E that serves IaaS revenue growth delivered in (t+1).
    eff_turn=[S['asset_turn_full']*S['utilization'][i] for i in range(n)]
    o['eff_asset_turn']=eff_turn
    iaas_next=[(o['rev_iaas'][i+1] if i+1<n else o['rev_iaas'][n-1]*(1+S['iaas_g_terminal'])) for i in range(n)]
    raw=[max(0.0,(iaas_next[i]-o['rev_iaas'][i])/eff_turn[i]) for i in range(n)]
    # Oracle funds only the share of new capacity not prepaid or supplied in kind by customers
    raw=[raw[i]*(1-S['cust_funded_capacity'][i]) for i in range(n)]
    # NOT smoothed. The path is lumpy because the DISCLOSED RPO conversion schedule is lumpy;
    # smoothing it would hide the mechanism. A 3-year rolling average is reported alongside.
    growth_capex=raw
    o['growth_capex']=growth_capex
    # depreciation and maintenance capex are mutually dependent -> solve iteratively
    capex=list(growth_capex); dep=[0.0]*n
    for _ in range(60):
        placed=[0.0]*n
        for i in range(n):
            if i<len(S['cip_release']): placed[i]+=PPE26['cip']*S['cip_release'][i]
            for j in range(i+1):
                k=i-j
                if k<len(S['capex_inservice_split']): placed[i]+=capex[j]*S['capex_inservice_split'][k]
        base_gross=PPE26['gross']-PPE26['cip']; base_nbv=base_gross-PPE26['accum_dep']
        dep_base=[max(0.0,min(base_nbv/5.0, base_nbv-(base_nbv/5.0)*i)) for i in range(n)]
        dep_new=[0.0]*n
        for i in range(n):
            for j in range(i+1):
                a=placed[j]
                e=a*S['capex_equip']/S['life_equip']; b=a*S['capex_bldg']/S['life_bldg']
                dep_new[i]+=(e+b)*(0.5 if j==i else 1.0)
        # impaired assets stop depreciating: relieve future depreciation over the residual life
        newdep=[max(0.0, dep_base[i]+dep_new[i]-sum(S['impairment'][:i])/5.0) for i in range(n)]
        newcapex=[growth_capex[i]+newdep[i]*S['maint_capex_pct_dep'][i] for i in range(n)]
        for i in range(n):     # committed orders: capex cannot collapse instantly
            newcapex[i]=max(newcapex[i], S['capex_min'][i])
            if i>0: newcapex[i]=max(newcapex[i], newcapex[i-1]*S['capex_floor_pct_prior'][i])
        if max(abs(newcapex[i]-capex[i]) for i in range(n))<1.0:
            capex, dep, o['inservice_additions'] = newcapex, newdep, placed; break
        capex, dep = newcapex, newdep
    o['capex']=capex; o['depreciation']=dep; o['dep_base']=dep_base; o['dep_new']=dep_new
    o['maint_capex']=[capex[i]-growth_capex[i] for i in range(n)]
    gross=[]; g=PPE26['gross']
    for i in range(n): g+=capex[i]; gross.append(g)
    o['ppe_gross']=gross
    accum=PPE26['accum_dep']; net=[]
    for i in range(n):
        accum+=dep[i]; net.append(gross[i]-accum-sum(S['impairment'][:i+1]))
    o['ppe_net']=net
    cip=PPE26['cip']; cips=[]
    for i in range(n):
        cip=cip+capex[i]-o['inservice_additions'][i]; cips.append(max(cip,0.0))
    o['cip_end']=cips
    # ---------- cost of revenue ----------
    o['dep_in_iaas']=[dep[i]*S['ocidep_share'][i] for i in range(n)]
    o['cost_iaas']=[o['rev_iaas'][i]*S['iaas_nondep_cost'][i]+o['dep_in_iaas'][i] for i in range(n)]
    o['gm_iaas']=[1-o['cost_iaas'][i]/o['rev_iaas'][i] for i in range(n)]
    o['cost_saas']=[o['rev_saas'][i]*(1-S['saas_gm'][i]) for i in range(n)]
    o['cost_sw']=[o['rev_support'][i]*(1-S['sup_gm'][i])+o['rev_license'][i]*(1-S['lic_gm'][i]) for i in range(n)]
    o['cost_services']=[o['rev_services'][i]*(1-S['svc_gm'][i]) for i in range(n)]
    o['cost_hardware']=[o['rev_hardware'][i]*(1-S['hw_gm'][i]) for i in range(n)]
    o['cost_cloudsw']=[o['cost_iaas'][i]+o['cost_saas'][i]+o['cost_sw'][i] for i in range(n)]
    o['cor_total']=[o['cost_cloudsw'][i]+o['cost_services'][i]+o['cost_hardware'][i] for i in range(n)]
    o['gross_profit']=[o['rev_total'][i]-o['cor_total'][i] for i in range(n)]
    o['gross_margin']=[o['gross_profit'][i]/o['rev_total'][i] for i in range(n)]
    # ---------- opex ----------
    o['opex_sm']=[o['rev_total'][i]*S['sm_pct'][i] for i in range(n)]
    o['opex_rd']=grow(H['opex_rd'][2],S['rd_growth']); o['opex_ga']=grow(H['opex_ga'][2],S['ga_growth'])
    o['amort_intang']=[AMORT_SCHED[f] for f in FY]
    o['restructuring']=[S['restructuring'][i]+S['impairment'][i] for i in range(n)]
    o['impairment']=S['impairment']
    o['sbc']=grow(H['sbc'][2],S['sbc_growth'])
    o['opex_total']=[o['cor_total'][i]+o['opex_sm'][i]+o['opex_rd'][i]+o['opex_ga'][i]
                     +o['amort_intang'][i]+o['restructuring'][i] for i in range(n)]
    o['op_income']=[o['rev_total'][i]-o['opex_total'][i] for i in range(n)]
    o['op_margin']=[o['op_income'][i]/o['rev_total'][i] for i in range(n)]
    # ---------- shares (needed for dividends) ----------
    # mandatory convertible converts 1/15/2029 -> 4.5 of FY29's 12 months, full from FY30
    pref_w=[0.0,0.0,4.5/12.0,1.0,1.0]
    sh=H['waso_diluted'][2]; shares=[]; atm=0.0
    for i in range(n):
        sh*= (1+S['dilution_sbc'])
        if S['equity_raise'][i]>0 and S['equity_price'][i]>0:
            add=S['equity_raise'][i]/S['equity_price'][i]; atm+=add
            sh+= add*(0.5 if i==0 else 1.0)
        shares.append(sh+PREF['shares_if_conv_at_mkt']*pref_w[i])
    o['shares_diluted']=shares; o['atm_shares']=atm
    o['shares_basic']=[s-55.0 for s in shares]
    o['pref_div']=[PREF['div_annual']*(1.0 if FY[i]<2029 else (7.5/12.0 if FY[i]==2029 else 0.0)) for i in range(n)]
    # ---------- debt / interest (tranche-tracked) ----------
    debt_open=BS26['debt_cur']+BS26['debt_nc']; cash_open=BS26['cash']+BS26['mkt_sec']
    debt=[0.0]*n; cash=[0.0]*n; interest=[0.0]*n; iss=[0.0]*n; intinc=[0.0]*n
    ni=[0.0]*n; ocf=[0.0]*n; taxes=[0.0]*n; pretax=[0.0]*n
    legacy_bal=debt_open; new_bal=0.0
    d_prev,c_prev=debt_open,cash_open
    for i in range(n):
        amort=DEBT_MAT[FY[i]]
        leg_end=max(0.0, legacy_bal-amort)
        x=0.0
        for _ in range(50):
            interest[i]=((legacy_bal+leg_end)/2)*S['rate_existing'] + (new_bal+x*0.5)*S['cost_new_debt']
            intinc[i]=((c_prev+max(c_prev,0))/2)*S['interest_income_rate']
            pretax[i]=o['op_income'][i]-interest[i]+intinc[i]-250.0
            taxes[i]=pretax[i]*S['tax_rate_gaap'][i]; ni[i]=pretax[i]-taxes[i]
            prev_rev=H['rev_total'][2] if i==0 else o['rev_total'][i-1]
            dnwc=-(o['rev_total'][i]-prev_rev)*S['nwc_pct_rev_change']
            ocf[i]=ni[i]+o['depreciation'][i]+o['amort_intang'][i]+o['sbc'][i]+S['impairment'][i]+dnwc+S['cust_prepay'][i]
            div=S['dividend_ps'][i]*o['shares_basic'][i]+o['pref_div'][i]
            need=o['capex'][i]+amort+div-ocf[i]-S['equity_raise'][i]-S['st_fin_capex'][i]+3000.0
            xn=max(0.0,need)
            if abs(xn-x)<1.0: x=xn; break
            x=xn
        iss[i]=x; new_bal=new_bal+x; legacy_bal=leg_end
        debt[i]=legacy_bal+new_bal
        div=S['dividend_ps'][i]*o['shares_basic'][i]+o['pref_div'][i]
        cash[i]=c_prev+ocf[i]+S['equity_raise'][i]+S['st_fin_capex'][i]+x-o['capex'][i]-amort-div
        d_prev,c_prev=debt[i],cash[i]
    o['debt']=debt; o['cash']=cash; o['interest_exp']=interest; o['interest_income']=intinc
    o['new_issuance']=iss; o['net_income']=ni; o['ocf']=ocf; o['tax']=taxes; o['pretax']=pretax
    o['fcf']=[ocf[i]-o['capex'][i] for i in range(n)]
    o['net_capex_outlay']=[o['capex'][i]-S['st_fin_capex'][i]-S['cust_prepay'][i] for i in range(n)]
    o['fcf_net_capex']=[o['ocf'][i]-S['cust_prepay'][i]-o['net_capex_outlay'][i] for i in range(n)]
    o['dividends']=[S['dividend_ps'][i]*o['shares_basic'][i] for i in range(n)]
    # ---------- EPS ----------
    o['ni_common']=[ni[i]-o['pref_div'][i] for i in range(n)]
    o['eps_gaap']=[o['ni_common'][i]/shares[i] for i in range(n)]
    o['ng_op_income']=[o['op_income'][i]+o['sbc'][i]+o['amort_intang'][i]+o['restructuring'][i] for i in range(n)]
    o['ng_pretax']=[o['pretax'][i]+o['sbc'][i]+o['amort_intang'][i]+o['restructuring'][i] for i in range(n)]
    o['ng_tax']=[o['ng_pretax'][i]*S['tax_rate_ng'][i] for i in range(n)]
    o['ng_ni']=[o['ng_pretax'][i]-o['ng_tax'][i] for i in range(n)]
    o['ng_ni_common']=[o['ng_ni'][i]-o['pref_div'][i] for i in range(n)]
    o['eps_ng']=[o['ng_ni_common'][i]/shares[i] for i in range(n)]
    o['ebitda']=[o['op_income'][i]+o['depreciation'][i]+o['amort_intang'][i] for i in range(n)]
    o['ebitda_ng']=[o['ng_op_income'][i]+o['depreciation'][i] for i in range(n)]
    o['net_debt']=[debt[i]-cash[i] for i in range(n)]
    o['nd_ebitda']=[o['net_debt'][i]/o['ebitda'][i] for i in range(n)]
    o['int_cov']=[(o['ebitda'][i]/(interest[i]-intinc[i]) if (interest[i]-intinc[i])>100 else float('nan')) for i in range(n)]
    # ---------- ROIC ----------
    ic=[]
    for i in range(n):
        prev=PPE26['net'] if i==0 else o['ppe_net'][i-1]
        ic.append((prev+o['ppe_net'][i])/2 + BS26['goodwill'] + BS26['rou_op'] + 5000)
    o['invested_capital']=ic
    o['nopat']=[o['op_income'][i]*(1-S['tax_rate_gaap'][i]) for i in range(n)]
    o['roic']=[o['nopat'][i]/ic[i] for i in range(n)]
    ic26=PPE26['net']+BS26['goodwill']+BS26['rou_op']+5000; nopat26=H['op_income'][2]*(1-0.126)
    o['roic_incremental']=[(o['nopat'][i]-nopat26)/max(1.0,ic[i]-ic26) for i in range(n)]
    # GROSS-basis ROIC. Net-book ROIC flatters a heavy-depreciation buildout as assets age,
    # so the gross measure is the one that answers "did the capex clear WACC".
    icg=[o['ppe_gross'][i]+BS26['goodwill']+BS26['rou_op']+5000 for i in range(n)]
    o['invested_capital_gross']=icg
    o['roic_gross']=[o['nopat'][i]/icg[i] for i in range(n)]
    icg26=PPE26['gross']+BS26['goodwill']+BS26['rou_op']+5000
    cum=[]; c=0.0
    for i in range(n): c+=o['capex'][i]; cum.append(c)
    o['cum_capex']=cum
    o['roic_incremental_gross']=[(o['nopat'][i]-nopat26)/cum[i] for i in range(n)]
    # ---------- unlevered / levered FCF for DCF ----------
    o['ufcf']=[o['nopat'][i]+o['depreciation'][i]+o['amort_intang'][i]+o['sbc'][i]*0
               -o['capex'][i]-(o['rev_total'][i]-(H['rev_total'][2] if i==0 else o['rev_total'][i-1]))*S['nwc_pct_rev_change']
               +S['cust_prepay'][i] for i in range(n)]
    o['fcfe']=[o['ocf'][i]-o['capex'][i]+S['st_fin_capex'][i]+o['new_issuance'][i]-DEBT_MAT[FY[i]] for i in range(n)]
    return o

R={s['name']:run(s) for s in (BASE,BULL,BEAR)}
S_BY={s['name']:s for s in (BASE,BULL,BEAR)}
json.dump({'hist':{k:(v if isinstance(v,list) else v) for k,v in H.items()},
           'res':{k:{kk:vv for kk,vv in v.items() if vv is not None} for k,v in R.items()},
           'fy':FY}, open('model_out.json','w'), default=float)

# ---------------- print ----------------
if __name__=="__main__":
  pass
import sys
if __name__!="__main__": sys.exit if False else None
_QUIET = (__name__!="__main__")
def _p(*a,**k):
  if not _QUIET: print(*a,**k)
print=_p
def row(lbl, vals, f="{:>10,.0f}"):
    print(f"{lbl:34s}"+"".join(f.format(v) for v in vals))
print("="*118); print("HISTORICALS (10-K sourced)  FY24 / FY25 / FY26"); print("="*118)
row("Total revenue",H['rev_total']); row("  IaaS",H['rev_iaas']); row("  SaaS",H['rev_saas'])
row("  Software license",H['rev_license']); row("  Software support",H['rev_support'])
row("  Services",H['rev_services']); row("  Hardware",H['rev_hardware'])
row("Gross margin %",[x*100 for x in H['gross_margin']],"{:>10.2f}")
row("Derived IaaS GM % (est.)",[x*100 for x in H['iaas_gm']],"{:>10.1f}")
row("Depreciation",H['depreciation']); row("Capex",H['capex']); row("FCF",H['fcf'])
row("EBITDA (GAAP)",H['ebitda'])
print()
for name in ('Base','Bull','Bear'):
    o=R[name]; print("="*118); print(f"{name.upper()} SCENARIO   FY27E  FY28E  FY29E  FY30E  FY31E"); print("="*118)
    row("Revenue",o['rev_total']); row("  growth %",[ (o['rev_total'][i]/(H['rev_total'][2] if i==0 else o['rev_total'][i-1])-1)*100 for i in range(5)],"{:>10.1f}")
    row("  from FY26 RPO runoff",o['rpo_runoff']); row("  from new bookings",o['rev_new_bookings'])
    row("  IaaS",o['rev_iaas']); row("  IaaS GM %",[x*100 for x in o['gm_iaas']],"{:>10.1f}")
    row("Gross margin %",[x*100 for x in o['gross_margin']],"{:>10.2f}")
    row("Depreciation",o['depreciation']); row("Capex (linked)",o['capex']); row("  growth capex",o['growth_capex']); row("  maintenance capex",o['maint_capex'])
    row("GAAP operating income",o['op_income']); row("  op margin %",[x*100 for x in o['op_margin']],"{:>10.1f}")
    row("Interest expense",o['interest_exp']); row("GAAP net income",o['net_income'])
    row("Diluted shares",o['shares_diluted']); row("GAAP EPS",o['eps_gaap'],"{:>10.2f}")
    row("Non-GAAP EPS",o['eps_ng'],"{:>10.2f}")
    row("Operating cash flow",o['ocf']); row("FCF (OCF - capex)",o['fcf'])
    row("FCF (Oracle net-capex def.)",o['fcf_net_capex'])
    row("Total debt",o['debt']); row("Net debt / EBITDA",o['nd_ebitda'],"{:>10.2f}")
    row("EBITDA / net interest",o['int_cov'],"{:>10.2f}")
    row("ROIC %",[x*100 for x in o['roic']],"{:>10.1f}")
    row("Incremental ROIC %(net bk)",[x*100 for x in o['roic_incremental']],"{:>10.1f}")
    row("ROIC % (gross basis)",[x*100 for x in o['roic_gross']],"{:>10.1f}")
    row("Incr. ROIC % (gross)",[x*100 for x in o['roic_incremental_gross']],"{:>10.1f}")
    row("Cumulative capex",o['cum_capex'])
    print()
