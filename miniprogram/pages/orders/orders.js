const API = getApp().globalData.apiBase;

Page({
  data: {
    orders: [],
    count: 0,
    total_amount: 0
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
          count: d.count,
          total_amount: d.total_amount
        });
      },
      fail: () => {
        wx.showToast({ title: "加载失败", icon: "error" });
      }
    });
  }
});
