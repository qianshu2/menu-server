const API = getApp().globalData.apiBase;

Page({
  data: {
    apiBase: API,
    dish: null,
    steps: [],
    loading: true
  },

  onLoad(options) {
    const name = decodeURIComponent(options.name || "");
    wx.setNavigationBarTitle({ title: name || "菜谱" });
    this.loadDish(name);
  },

  loadDish(name) {
    wx.request({
      url: API + "/dish/" + encodeURIComponent(name),
      success: (res) => {
        if (res.data.code === 200) {
          const dish = res.data.data;
          // 步骤按换行拆成数组，方便逐条展示
          const steps = (dish.steps || "").split("\n").filter(s => s.trim());
          this.setData({ dish, steps, loading: false });
        } else {
          this.setData({ loading: false });
          wx.showToast({ title: "暂无菜谱", icon: "none" });
        }
      },
      fail: () => {
        this.setData({ loading: false });
        wx.showToast({ title: "加载失败", icon: "error" });
      }
    });
  }
});
