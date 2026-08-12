const { request } = require("../../utils/request.js");

function todayStr() {
  const d = new Date();
  const m = (d.getMonth() + 1).toString().padStart(2, "0");
  const day = d.getDate().toString().padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

Page({
  data: {
    orders: [],
    count: 0,
    // 饮食日历
    weekdays: ["日", "一", "二", "三", "四", "五", "六"],
    calYear: new Date().getFullYear(),
    calMonth: new Date().getMonth() + 1,
    calCells: [],
    streak: 0,
    monthCount: 0
  },

  onShow() {
    this.loadOrders();
    this.loadCalendar();
  },

  async loadOrders() {
    try {
      const res = await request("/orders");
      const d = res.data;
      this.setData({
        orders: d.data,
        count: d.count
      });
    } catch (e) {
      // 网络错误由 request 统一弹 Toast
    }
  },

  // ===== 饮食日历 =====
  async loadCalendar() {
    const y = this.data.calYear, m = this.data.calMonth;
    try {
      const res = await request(`/orders/calendar?year=${y}&month=${m}`);
      const d = res.data.data || {};
      const cells = this.buildCells(d.year || y, d.month || m, d.days || {});
      this.setData({
        calCells: cells,
        streak: d.streak || 0,
        monthCount: d.monthTotal || 0,
        calYear: d.year || y,
        calMonth: d.month || m
      });
    } catch (e) {
      // 日历失败不阻断下方记录列表
    }
  },

  // 构造月历格子：前导空格 + 日期 + 末行补齐
  buildCells(year, month, daysMap) {
    const first = new Date(year, month - 1, 1);
    const startW = first.getDay(); // 0=周日
    const daysInMonth = new Date(year, month, 0).getDate();
    const t = new Date();
    const tY = t.getFullYear(), tM = t.getMonth() + 1, tD = t.getDate();
    const cells = [];
    for (let i = 0; i < startW; i++) cells.push({ empty: true, key: "e" + i });
    for (let day = 1; day <= daysInMonth; day++) {
      const key = String(day).padStart(2, "0");
      cells.push({
        empty: false,
        key,
        day,
        count: daysMap[key] || 0,
        isToday: (year === tY && month === tM && day === tD)
      });
    }
    while (cells.length % 7 !== 0) cells.push({ empty: true, key: "t" + cells.length });
    return cells;
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

  // 清除当日记录（带二次确认），便于换菜
  clearToday() {
    const today = todayStr();
    wx.showModal({
      title: "清除当日记录",
      content: "将删除今天记录的所有菜品，方便重新选菜。确定吗？",
      confirmColor: "#ff6b35",
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await request("/clear-orders", { method: "POST", data: { date: today } });
          wx.showToast({ title: "已清除当日", icon: "none" });
          this.loadOrders();
        } catch (e) {
          wx.showToast({ title: "清除失败", icon: "error" });
        }
      }
    });
  }
});
