const API = getApp().globalData.apiBase;

// 取本地（中国时区）今天的日期字符串 YYYY-MM-DD
function todayStr() {
  const d = new Date();
  const m = (d.getMonth() + 1).toString().padStart(2, "0");
  const day = d.getDate().toString().padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

Page({
  data: {
    apiBase: API,
    today: "",
    groups: [],     // [{ dish, items: [{ text, checked, main }] }]
    bought: 0,
    total: 0,
    dishCount: 0,
    loading: true,
    empty: false
  },

  onShow() {
    this.loadShopping();
  },

  loadShopping() {
    const today = todayStr();
    // 读取今日已勾选状态（按日期隔离），以食材文本为键
    const checkedList = wx.getStorageSync("shopping_" + today) || [];
    const checkedSet = new Set(checkedList);

    wx.request({
      url: API + "/orders",
      success: (res) => {
        const all = (res.data && res.data.data) || [];
        // 仅取「今天」的记录（created_at 形如 2026-07-14 10:00:00）
        // 注：后端按服务器时间存储，若在凌晨 0-8 点记录可能存在跨日偏差
        const todays = all.filter(o => (o.created_at || "").startsWith(today));

        if (todays.length === 0) {
          this.setData({ today, loading: false, empty: true, groups: [], bought: 0, total: 0, dishCount: 0 });
          return;
        }

        // 保持菜品出现顺序（去重）
        const dishNames = [];
        const seenDish = new Set();
        todays.forEach(o => {
          if (!seenDish.has(o.dish_name)) {
            seenDish.add(o.dish_name);
            dishNames.push(o.dish_name);
          }
        });

        this.fetchRecipes(dishNames, today, checkedSet);
      },
      fail: () => {
        wx.showToast({ title: "加载失败", icon: "error" });
        this.setData({ loading: false });
      }
    });
  },

  // 逐道菜拉取食材，按菜品分组；每道菜第一个食材视为主材，排在最前
  fetchRecipes(names, today, checkedSet) {
    let done = 0;
    const total = names.length;
    const groups = [];

    const finish = () => {
      let bought = 0, totalCount = 0;
      groups.forEach(g => g.items.forEach(it => {
        totalCount++;
        if (it.checked) bought++;
      }));
      this.setData({
        groups,
        today,
        dishCount: groups.length,
        bought,
        total: totalCount,
        loading: false,
        empty: groups.length === 0
      });
    };

    if (total === 0) { finish(); return; }

    names.forEach(name => {
      wx.request({
        url: API + "/dish/" + encodeURIComponent(name),
        success: (r) => {
          let items = [];
          if (r.data && r.data.code === 200) {
            const recipe = r.data.data.recipe || "";
            // 食材按 、 或 ， 拆分，保持原顺序（主材通常列在第一个）
            const parts = recipe.split(/[、，]/).map(s => s.trim()).filter(s => s);
            items = parts.map((p, i) => ({
              text: p,
              checked: checkedSet.has(p),
              main: i === 0
            }));
          }
          groups.push({ dish: name, items });
          done++;
          if (done === total) finish();
        },
        fail: () => {
          groups.push({ dish: name, items: [] });
          done++;
          if (done === total) finish();
        }
      });
    });
  },

  // 点击某一项：切换勾选 + 划线（按食材文本跨菜品联动），并持久化
  toggleItem(e) {
    const text = e.currentTarget.dataset.text;
    let bought = 0;
    const groups = this.data.groups.map(g => {
      const items = g.items.map(it =>
        it.text === text ? { ...it, checked: !it.checked } : it
      );
      return { ...g, items };
    });
    groups.forEach(g => g.items.forEach(it => { if (it.checked) bought++; }));
    this.setData({ groups, bought });

    const checkedList = [];
    groups.forEach(g => g.items.forEach(it => { if (it.checked) checkedList.push(it.text); }));
    wx.setStorageSync("shopping_" + this.data.today, checkedList);
  },

  clearChecked() {
    const groups = this.data.groups.map(g => ({
      ...g,
      items: g.items.map(it => ({ ...it, checked: false }))
    }));
    this.setData({ groups, bought: 0 });
    wx.setStorageSync("shopping_" + this.data.today, []);
    wx.showToast({ title: "已清空勾选", icon: "none" });
  },

  // 清除当日记录（带二次确认），便于换菜后重新生成清单
  clearToday() {
    wx.showModal({
      title: "清除当日记录",
      content: "将删除今天记录的所有菜品，方便重新选菜。确定吗？",
      confirmColor: "#ff6b35",
      success: (res) => {
        if (res.confirm) this.doClearToday();
      }
    });
  },

  doClearToday() {
    wx.request({
      url: API + "/clear-orders",
      method: "POST",
      data: { date: this.data.today },
      success: () => {
        wx.removeStorageSync("shopping_" + this.data.today);
        this.setData({ groups: [], bought: 0, total: 0, dishCount: 0, empty: true });
        wx.showToast({ title: "已清除，去重新选菜", icon: "none" });
      },
      fail: () => wx.showToast({ title: "清除失败", icon: "error" })
    });
  },

  goRecord() {
    wx.switchTab({ url: "/pages/index/index" });
  }
});
