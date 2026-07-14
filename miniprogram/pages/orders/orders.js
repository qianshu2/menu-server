const API = getApp().globalData.apiBase;

function todayStr() {
  const d = new Date();
  const m = (d.getMonth() + 1).toString().padStart(2, "0");
  const day = d.getDate().toString().padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

Page({
  data: {
    orders: [],
    count: 0
  },

  onShow() {
    this.loadOrders();
  },

  loadOrders() {
    wx.request({
      url: API + "/orders",
      success: (res) => {
        const d = res.data;
        this.setData({
          orders: d.data,
          count: d.count
        });
      },
      fail: () => {
        wx.showToast({ title: "加载失败", icon: "error" });
      }
    });
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
      success: (res) => {
        if (!res.confirm) return;
        wx.request({
          url: API + "/clear-orders",
          method: "POST",
          data: { date: today },
          success: () => {
            wx.showToast({ title: "已清除当日", icon: "none" });
            this.loadOrders();
          },
          fail: () => wx.showToast({ title: "清除失败", icon: "error" })
        });
      }
    });
  }
});
