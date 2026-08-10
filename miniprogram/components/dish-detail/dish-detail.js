Component({
  properties: {
    visible: {
      type: Boolean,
      value: false
    },
    dish: {
      type: Object,
      value: null
    }
  },

  data: {
    apiBase: getApp().globalData.apiBase,
    placeholder: "../../images/cats/xiaoxia.jpg",
    heroLoaded: false,
    heroError: false
  },

  // 切换菜品时重置图片加载状态
  observers: {
    "dish": function () {
      this.setData({ heroLoaded: false, heroError: false });
    }
  },

  methods: {
    // 点击遮罩关闭
    close() {
      this.triggerEvent("close");
    },

    // 阻止冒泡，避免点卡片内容意外关掉弹层
    noop() {},

    // 大图加载完成 / 失败
    onHeroLoad() {
      this.setData({ heroLoaded: true });
    },
    onHeroError() {
      this.setData({ heroError: true });
    },

    // 想吃
    onAdd() {
      this.triggerEvent("add", { name: this.data.dish.name });
    },

    // 查看做法
    onRecipe() {
      this.triggerEvent("recipe", { name: this.data.dish.name });
    }
  }
});
