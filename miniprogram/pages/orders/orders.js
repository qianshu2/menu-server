const { request } = require("../../utils/request.js");

function todayStr() {
  const d = new Date();
  const m = (d.getMonth() + 1).toString().padStart(2, "0");
  const day = d.getDate().toString().padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

// ===== 农历 / 二十四节气（1900-2100）=====
const lunarInfo = [0x04bd8,0x04ae0,0x0a570,0x054d5,0x0d260,0x0d950,0x16554,0x056a0,0x09ad0,0x055d2,
0x04ae0,0x0a5b6,0x0a4d0,0x0d250,0x1d255,0x0b540,0x0d6a0,0x0ada2,0x095b0,0x14977,
0x04970,0x0a4b0,0x0b4b5,0x06a50,0x06d40,0x1ab54,0x02b60,0x09570,0x052f2,0x04970,
0x06566,0x0d4a0,0x0ea50,0x06e95,0x05ad0,0x02b60,0x186e3,0x092e0,0x1c8d7,0x0c950,
0x0d4a0,0x1d8a6,0x0b550,0x056a0,0x1a5b4,0x025d0,0x092d0,0x0d2b2,0x0a950,0x0b557,
0x06ca0,0x0b550,0x15355,0x04da0,0x0a5b0,0x14573,0x052b0,0x0a9a8,0x0e950,0x06aa0,
0x0aea6,0x0ab50,0x04b60,0x0aae4,0x0a570,0x05260,0x0f263,0x0d950,0x05b57,0x056a0,
0x096d0,0x04dd5,0x04ad0,0x0a4d0,0x0d4d4,0x0d250,0x0d558,0x0b540,0x0b6a0,0x195a6,
0x095b0,0x049b0,0x0a974,0x0a4b0,0x0b27a,0x06a50,0x06d40,0x0af46,0x0ab60,0x09570,
0x04af5,0x04970,0x064b0,0x074a3,0x0ea50,0x06b58,0x055c0,0x0ab60,0x096d5,0x092e0,
0x0c960,0x0d954,0x0d4a0,0x0da50,0x07552,0x056a0,0x0abb7,0x025d0,0x092d0,0x0cab5,
0x0a950,0x0b4a0,0x0baa4,0x0ad50,0x055d9,0x04ba0,0x0a5b0,0x15176,0x052b0,0x0a930,
0x07954,0x06aa0,0x0ad50,0x05b52,0x04b60,0x0a6e6,0x0a4e0,0x0d260,0x0ea65,0x0d530,
0x05aa0,0x076a3,0x096d0,0x04afb,0x04ad0,0x0a4d0,0x1d0b6,0x0d250,0x0d520,0x0dd45,
0x0b5a0,0x056d0,0x055b2,0x049b0,0x0a577,0x0a4b0,0x0aa50,0x1b255,0x06d20,0x0ada0,
0x14b63,0x09370,0x049f8,0x04970,0x064b0,0x168a6,0x0ea50,0x06b20,0x1a6c4,0x0aae0,
0x0a2e0,0x0d2e3,0x0c960,0x0d557,0x0d4a0,0x0da50,0x05d55,0x056a0,0x0a6d0,0x055d4,
0x052d0,0x0a9b8,0x0a950,0x0b4a0,0x0b6a6,0x0ad50,0x055a0,0x0aba4,0x0a5b0,0x052b0,
0x0b273,0x06930,0x07337,0x06aa0,0x0ad50,0x14b55,0x04b60,0x0a570,0x054e4,0x0d160,
0x0e968,0x0d520,0x0daa0,0x16aa6,0x056d0,0x04ae0,0x0a9d4,0x0a2d0,0x0d150,0x0f250,
0x0d520];
const lunarDayCN = ["初一","初二","初三","初四","初五","初六","初七","初八","初九","初十","十一","十二","十三","十四","十五","十六","十七","十八","十九","二十","廿一","廿二","廿三","廿四","廿五","廿六","廿七","廿八","廿九","三十"];
const termCN = ["小寒","大寒","立春","雨水","惊蛰","春分","清明","谷雨","立夏","小满","芒种","夏至","小暑","大暑","立秋","处暑","白露","秋分","寒露","霜降","立冬","小雪","大雪","冬至"];
const sTermInfo = [0,21208,42467,63836,85337,107014,128867,150921,173149,195551,218072,240693,263343,285989,308563,331033,353350,375494,397447,419210,440795,462224,483532,504758];

function lYearDays(y){ let s=348; for(let i=0x8000;i>0x8;i>>=1) s+=(lunarInfo[y-1900]&i)?1:0; return s+leapDays(y); }
function leapMonth(y){ return lunarInfo[y-1900]&0xf; }
function leapDays(y){ return leapMonth(y)?(lunarInfo[y-1900]&0x10000?30:29):0; }
function monthDays(y,m){ return (lunarInfo[y-1900]&(0x10000>>m))?30:29; }

function solarToLunar(y,m,d){
  if(y<1900||y>2100) return {lMonth:m,lDay:d};
  const base=new Date(1900,0,31), obj=new Date(y,m-1,d);
  let offset=Math.round((obj-base)/86400000), ly=1900, temp=0;
  for(;ly<2101&&offset>0;ly++){ temp=lYearDays(ly); offset-=temp; }
  if(offset<0){ offset+=temp; ly--; }
  const leap=leapMonth(ly); let isLeap=false, lm=1;
  for(;lm<13&&offset>0;lm++){
    if(leap>0&&lm===(leap+1)&&!isLeap){ lm--; isLeap=true; temp=leapDays(ly); }
    else temp=monthDays(ly,lm);
    if(isLeap&&lm===(leap+1)) isLeap=false;
    offset-=temp;
  }
  if(offset===0&&leap>0&&lm===leap+1){ if(isLeap) isLeap=false; else { isLeap=true; lm--; } }
  if(offset<0){ offset+=temp; lm--; }
  return {lMonth:lm, lDay:offset+1};
}

function getTermDate(y,n){
  const off=new Date((31556925974.7*(y-1900)+sTermInfo[n]*60000)+Date.UTC(1900,0,6,2,5));
  return { m: off.getUTCMonth()+1, d: off.getUTCDate() };
}

// 返回某日显示文本：优先节气 > 农历节日 > 农历日期
function getCellLunar(y,m,d){
  let term="";
  for(let n=0;n<24;n++){ const t=getTermDate(y,n); if(t.m===m&&t.d===d){ term=termCN[n]; break; } }
  const L=solarToLunar(y,m,d);
  let fest="";
  if(L.lMonth===1&&L.lDay===1) fest="春节";
  else if(L.lMonth===1&&L.lDay===15) fest="元宵";
  else if(L.lMonth===2&&L.lDay===2) fest="龙抬头";
  else if(L.lMonth===5&&L.lDay===5) fest="端午";
  else if(L.lMonth===7&&L.lDay===7) fest="七夕";
  else if(L.lMonth===7&&L.lDay===15) fest="中元";
  else if(L.lMonth===8&&L.lDay===15) fest="中秋";
  else if(L.lMonth===9&&L.lDay===9) fest="重阳";
  else if(L.lMonth===12&&L.lDay===8) fest="腊八";
  else if(L.lMonth===12&&L.lDay===23) fest="小年";
  return { text: term||fest||lunarDayCN[L.lDay-1], term: term!=="" };
}

Page({
  data: {
    weekdays: ["日", "一", "二", "三", "四", "五", "六"],
    calYear: new Date().getFullYear(),
    calMonth: new Date().getMonth() + 1,
    calCells: [],
    calDaysMap: {},
    // 选中日期（YYYY-MM-DD）及当日记录
    selectedDate: "",
    selLabel: "",
    dayOrders: [],
    dayOrdersCount: 0,
    streak: 0,
    monthCount: 0
  },

  onShow() {
    this.loadCalendar();
  },

  // ===== 饮食日历 =====
  async loadCalendar() {
    const y = this.data.calYear, m = this.data.calMonth;
    // 首次进入默认选中今天
    const selDate = this.data.selectedDate || todayStr();
    try {
      const res = await request(`/orders/calendar?year=${y}&month=${m}`);
      const d = res.data.data || {};
      const year = d.year || y, month = d.month || m;
      const cells = this.buildCells(year, month, d.days || {}, selDate);
      this.setData({
        calCells: cells,
        calDaysMap: d.days || {},
        streak: d.streak || 0,
        monthCount: d.monthTotal || 0,
        calYear: year,
        calMonth: month,
        selectedDate: selDate
      });
      this.loadDayOrders(selDate);
    } catch (e) {
      // 日历失败不阻断下方记录列表
    }
  },

  // 构造月历格子：前导空格 + 日期 + 末行补齐
  buildCells(year, month, daysMap, selDate) {
    const first = new Date(year, month - 1, 1);
    const startW = first.getDay(); // 0=周日
    const daysInMonth = new Date(year, month, 0).getDate();
    const t = new Date();
    const tY = t.getFullYear(), tM = t.getMonth() + 1, tD = t.getDate();
    const cells = [];
    for (let i = 0; i < startW; i++) cells.push({ empty: true, key: "e" + i });
    for (let day = 1; day <= daysInMonth; day++) {
      const key = String(day).padStart(2, "0");
      const wd = new Date(year, month - 1, day).getDay(); // 0=周日,6=周六
      const lun = getCellLunar(year, month, day);
      const dateKey = `${year}-${String(month).padStart(2, "0")}-${key}`;
      cells.push({
        empty: false,
        key,
        day,
        count: daysMap[key] || 0,
        isToday: (year === tY && month === tM && day === tD),
        isWeekend: (wd === 0 || wd === 6),
        isSelected: (dateKey === selDate),
        lunar: lun.text,
        term: lun.term
      });
    }
    while (cells.length % 7 !== 0) cells.push({ empty: true, key: "t" + cells.length });
    return cells;
  },

  // 点击某天：高亮并更新下方当日记录
  onTapDay(e) {
    const day = e.currentTarget.dataset.day;
    if (!day) return; // 空白格
    const y = this.data.calYear, m = this.data.calMonth;
    const date = `${y}-${String(m).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    this.selectDay(date);
  },

  selectDay(date) {
    this.setData({ selectedDate: date });
    const cells = this.buildCells(this.data.calYear, this.data.calMonth, this.data.calDaysMap, date);
    this.setData({ calCells: cells });
    this.loadDayOrders(date);
  },

  // 拉取某日记录，并更新标题（周几 + 农历/节气）
  async loadDayOrders(date) {
    if (!date) { this.setData({ dayOrders: [], dayOrdersCount: 0, selLabel: "" }); return; }
    const [y, m, d] = date.split("-").map(Number);
    const wd = new Date(y, m - 1, d).getDay();
    const lun = getCellLunar(y, m, d);
    this.setData({ selLabel: `${m}月${d}日 周${this.data.weekdays[wd]} · ${lun.text}` });
    try {
      const res = await request(`/orders?date=${date}`);
      const arr = res.data.data || [];
      this.setData({ dayOrders: arr, dayOrdersCount: arr.length });
    } catch (e) {
      this.setData({ dayOrders: [], dayOrdersCount: 0 });
    }
  },

  prevMonth() {
    let y = this.data.calYear, m = this.data.calMonth - 1;
    if (m < 1) { m = 12; y--; }
    this.setData({ calYear: y, calMonth: m }, () => this.loadCalendar());
  },

  nextMonth() {
    let y = this.data.calYear, m = this.data.calMonth + 1;
    if (m > 12) { m = 1; y++; }
    this.setData({ calYear: y, calMonth: m }, () => this.loadCalendar());
  },

  goShopping() {
    wx.switchTab({ url: "/pages/shopping/shopping" });
  },

  // 清除选中日记录（带二次确认），便于换菜
  clearSelected() {
    const date = this.data.selectedDate;
    if (!date) return;
    wx.showModal({
      title: "清除当日记录",
      content: `将删除 ${date} 记录的所有菜品，方便重新选菜。确定吗？`,
      confirmColor: "#ff6b35",
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await request("/clear-orders", { method: "POST", data: { date } });
          wx.showToast({ title: "已清除当日", icon: "none" });
          this.loadDayOrders(date);
          this.loadCalendar();
        } catch (e) {
          wx.showToast({ title: "清除失败", icon: "error" });
        }
      }
    });
  }
});
