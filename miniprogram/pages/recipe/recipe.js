const { request, getBase } = require("../../utils/request.js");

Page({
  data: {
    apiBase: getBase(),
    dish: null,
    steps: [],
    loading: true,
    placeholder: "../../images/cats/xiaoxia.jpg",
    imgLoaded: false,
    imgError: false
  },

  onLoad(options) {
    const name = decodeURIComponent(options.name || "");
    wx.setNavigationBarTitle({ title: name || "菜谱" });
    this.loadDish(name);
  },

  async loadDish(name) {
    this.setData({ imgLoaded: false, imgError: false });
    try {
      const res = await request("/dish/" + encodeURIComponent(name));
      if (res.data.code === 200) {
        const dish = res.data.data;
        // 步骤按换行拆成数组，方便逐条展示
        const steps = (dish.steps || "").split("\n").filter(s => s.trim());
        this.setData({ dish, steps, loading: false });
      } else {
        this.setData({ loading: false });
        wx.showToast({ title: "暂无菜谱", icon: "none" });
      }
    } catch (e) {
      this.setData({ loading: false });
      // 网络错误由 request 统一弹 Toast
    }
  },

  onImgLoad() {
    this.setData({ imgLoaded: true });
  },

  onImgError() {
    this.setData({ imgError: true });
  }
});
