const { request, getBase } = require("../../utils/request.js");

// 取本地（中国时区）今天的日期字符串 YYYY-MM-DD
function todayStr() {
  const d = new Date();
  const m = (d.getMonth() + 1).toString().padStart(2, "0");
  const day = d.getDate().toString().padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

// 清洗食材名：去掉尾部的用量/计量单位，如「生抽3勺」→「生抽」、「五花肉500g」→「五花肉」、「醋一勺」→「醋」
// 采用尾部扫描算法（而非单一正则），可稳健区分「八角」(菜名) 与「2颗」(用量)、「土豆块/鱼片」(菜名) 与用量
function cleanName(raw) {
  let t = (raw || "").trim();
  if (!t) return t;
  const units = "勺汤匙茶匙克g千克kg公斤毫升ml升l颗个只条根片块瓣把束段节盒瓶包袋罐碗盆盘杯滴撮";
  const size = "小大中";
  const num = "0123456789零一二三四五六七八九十百千两半几多";
  const desc = ["适量", "少许", "若干", "一些", "一点", "少量", "大量", "多点"];
  const isUnit = c => units.includes(c);
  const isNum = c => num.includes(c) || (c >= "0" && c <= "9");
  const isSize = c => size.includes(c);
  const isLatinUnit = c => /[a-z]/i.test(c) && units.includes(c.toLowerCase());

  // 1) 尾部描述词（适量/少许/…）
  for (let k = 0; k < desc.length; k++) {
    const d = desc[k];
    if (t.endsWith(d)) return t.slice(0, t.length - d.length).trim();
  }

  // 2) 尾部「数字+可选尺寸+单位」：末位必须是单位，且向前扫描必须遇到至少一个数字，才整体剥离
  const last = t[t.length - 1];
  if (isUnit(last)) {
    let j = t.length - 2;
    // 向前跳过：尺寸(小/大/中)、数字、小数点、空白、拉丁单位(g/ml/kg…)；遇中文单位(片/块…)则停（可能是菜名结尾）
    while (j >= 0 && (isSize(t[j]) || isNum(t[j]) || t[j] === "." || t[j] === " " || t[j] === "　" || isLatinUnit(t[j]))) j--;
    const qty = t.slice(j + 1);
    if (qty.split("").some(isNum)) {
      const name = t.slice(0, j + 1).trim();
      return name || t; // 防御：整串都是用量则保留原名
    }
  }
  return t;
}

Page({
  data: {
    apiBase: getBase(),
    today: "",
    groups: [],     // [{ dish, items: [{ text, checked, main, staple, isSeasoning }], isSeasoning }]
    bought: 0,
    total: 0,
    dishCount: 0,
    loading: true,
    empty: false,
    // 补充调料 UI
    showAdd: false,
    addInput: "",
    seasoningLib: [],   // 我的调料库（所有曾补充过的，去重展示）
    showStapleHint: false, // 是否存在常备项，用于提示与按钮
    // 家庭共享（路线 A：房间码，无登录）
    shareCode: "",       // 当前所在房间码（空=未加入）
    shareJoinInput: "",  // 加入时输入的码
    shareItems: [],      // [{ dish_name, quantity, added_by }]
    shareName: "我"      // 在共享房间里的昵称
  },

  onShow() {
    this.loadShopping();
    this.loadShare();
  },

  async loadShopping() {
    const today = todayStr();
    const checkedList = wx.getStorageSync("shopping_" + today) || [];
    const checkedSet = new Set(checkedList);
    const lib = wx.getStorageSync("seasoning_lib") || [];
    const staple = wx.getStorageSync("seasoning_staple") || [];
    const stapleSet = new Set(staple);

    try {
      const res = await request("/orders?date=" + today);
      const all = (res.data && res.data.data) || [];
      // 仅取「今天」的记录（created_at 形如 2026-07-14 10:00:00）
      // 注：后端按服务器时间存储，若在凌晨 0-8 点记录可能存在跨日偏差
      const todays = all.filter(o => (o.created_at || "").startsWith(today));

      // 既无今日菜品、也无调料库时，才算空
      if (todays.length === 0 && lib.length === 0) {
        this.setData({ today, loading: false, empty: true, groups: [], bought: 0, total: 0, dishCount: 0, seasoningLib: lib });
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

      this.fetchRecipes(dishNames, today, { checkedSet, lib, stapleSet });
    } catch (e) {
      wx.showToast({ title: "加载失败", icon: "error" });
      this.setData({ loading: false });
    }
  },

  // 批量拉取各道菜食材，按菜品分组；每道菜第一个食材视为主材，排在最前
  async fetchRecipes(names, today, ctx) {
    // 一次请求拿全部菜谱，替代原先逐道菜 GET /dish/<name> 的 N+1 请求
    let recipeMap = {};
    if (names.length > 0) {
      const namesParam = names.map(encodeURIComponent).join(",");
      try {
        const res = await request("/dishes/recipes?names=" + namesParam);
        recipeMap = (res.data && res.data.data) || {};
      } catch (e) {
        // 菜谱拉取失败不阻断整体，下方按空处理
      }
    }

    const groups = names.map(name => {
      const d = recipeMap[name] || {};
      const recipe = d.recipe || "";
      const parts = recipe.split(/[、，]/).map(s => s.trim()).filter(s => s);
      // 清洗用量后缀并去重(同一道菜内)，主材(首个原始项)保持置顶；丢弃清洗后为空的项
      const seen = new Set();
      const items = parts
        .map((p, i) => ({ clean: cleanName(p), main: i === 0 }))
        .filter(o => o.clean)
        .filter(o => { if (seen.has(o.clean)) return false; seen.add(o.clean); return true; })
        .map(o => ({
          text: o.clean,
          checked: ctx.checkedSet.has(o.clean),
          main: o.main
        }));
      return { dish: name, items, isSeasoning: false };
    });

    // 追加「我的调料」分组
    const seasoningGroup = this.buildSeasoningGroup(ctx);
    if (seasoningGroup) groups.push(seasoningGroup);

    let bought = 0, totalCount = 0, hasStaple = false;
    groups.forEach(g => g.items.forEach(it => {
      totalCount++;
      if (it.checked) bought++;
      if (it.staple) hasStaple = true;
    }));
    this.setData({
      groups,
      today,
      dishCount: groups.filter(g => !g.isSeasoning).length,
      bought,
      total: totalCount,
      loading: false,
      empty: false,
      seasoningLib: ctx.lib,
      showStapleHint: hasStaple
    });
  },

  // 构建「我的调料」分组：勾选过(在常备库)的默认已购，否则按当天勾选记录
  buildSeasoningGroup(ctx) {
    const lib = ctx.lib;
    if (!lib || lib.length === 0) return null;
    const items = lib.map(text => {
      const staple = ctx.stapleSet.has(text);
      const checked = staple ? true : ctx.checkedSet.has(text);
      return { text, checked, staple, isSeasoning: true };
    });
    return { dish: "🧂 我的调料", items, isSeasoning: true };
  },

  // 点击某一项：切换勾选 + 划线（按食材文本跨菜品联动），并持久化 + 同步常备库
  toggleItem(e) {
    const text = e.currentTarget.dataset.text;
    let bought = 0;
    const groups = this.data.groups.map(g => {
      const items = g.items.map(it =>
        it.text === text ? Object.assign({}, it, { checked: !it.checked }) : it
      );
      return Object.assign({}, g, { items: items });
    });
    groups.forEach(g => g.items.forEach(it => { if (it.checked) bought++; }));
    this.setData({ groups, bought });
    this.persistChecked(groups);
    this.syncStaple(groups);
  },

  // 同步常备库：调料组中被勾选的项入常备库，取消的移出（菜谱食材不受影响）
  syncStaple(groups) {
    const staple = wx.getStorageSync("seasoning_staple") || [];
    const stapleSet = new Set(staple);
    let changed = false;
    groups.forEach(g => {
      if (!g.isSeasoning) return;
      g.items.forEach(it => {
        if (it.checked && !stapleSet.has(it.text)) { stapleSet.add(it.text); changed = true; }
        if (!it.checked && stapleSet.has(it.text)) { stapleSet.delete(it.text); changed = true; }
      });
    });
    if (changed) wx.setStorageSync("seasoning_staple", Array.from(stapleSet));
  },

  persistChecked(groups) {
    const checkedList = [];
    groups.forEach(g => g.items.forEach(it => { if (it.checked) checkedList.push(it.text); }));
    wx.setStorageSync("shopping_" + this.data.today, checkedList);
  },

  clearChecked() {
    const groups = this.data.groups.map(g => Object.assign({}, g, {
      items: g.items.map(it => Object.assign({}, it, { checked: false }))
    }));
    this.setData({ groups, bought: 0 });
    wx.setStorageSync("shopping_" + this.data.today, []);
    wx.showToast({ title: "已清空勾选", icon: "none" });
  },

  // 常备项（默认已购）一键标记为要买：取消勾选并移出常备库
  clearStaple() {
    const staple = wx.getStorageSync("seasoning_staple") || [];
    const stapleSet = new Set(staple);
    const groups = this.data.groups.map(g => {
      if (!g.isSeasoning) return g;
      const items = g.items.map(it => stapleSet.has(it.text) ? Object.assign({}, it, { checked: false }) : it);
      return Object.assign({}, g, { items: items });
    });
    this.setData({ groups });
    this.persistChecked(groups);
    wx.setStorageSync("seasoning_staple", []);
    wx.showToast({ title: "常备已标记为要买", icon: "none" });
  },

  // ===== 补充调料 =====
  toggleAdd() {
    this.setData({ showAdd: !this.data.showAdd, addInput: "" });
  },
  onAddInput(e) {
    this.setData({ addInput: e.detail.value });
  },
  // 新增/补充一个调料（输入或点 chip 都会走到这里）。补充仅加入清单，勾选后才入常备库
  addSeasoning(e) {
    const name = (e.currentTarget.dataset.name || this.data.addInput || "").trim();
    if (!name) return;
    let lib = wx.getStorageSync("seasoning_lib") || [];
    if (!lib.includes(name)) lib.push(name);
    wx.setStorageSync("seasoning_lib", lib);

    let targetGroups = this.data.groups;
    const hasGroup = targetGroups.some(g => g.isSeasoning);
    if (!hasGroup) {
      targetGroups = targetGroups.concat([{
        dish: "🧂 我的调料",
        items: [{ text: name, checked: false, staple: false, isSeasoning: true }],
        isSeasoning: true
      }]);
    } else {
      targetGroups = targetGroups.map(g => {
        if (!g.isSeasoning) return g;
        if (g.items.some(it => it.text === name)) return g;
        return Object.assign({}, g, {
          items: g.items.concat([{ text: name, checked: false, staple: false, isSeasoning: true }])
        });
      });
    }

    let bought = 0, total = 0, hasStaple = false;
    targetGroups.forEach(g => g.items.forEach(it => {
      total++; if (it.checked) bought++; if (it.staple) hasStaple = true;
    }));

    this.setData({
      groups: targetGroups,
      seasoningLib: lib,
      bought,
      total,
      empty: targetGroups.length > 0 ? false : this.data.empty,
      showStapleHint: hasStaple,
      addInput: "",
      showAdd: false
    });
    wx.showToast({ title: "已加入：" + name, icon: "none" });
  },

  // 清除当日记录（带二次确认），便于换菜后重新生成清单（不清除调料库）
  clearToday() {
    wx.showModal({
      title: "清除当日记录",
      content: "将删除今天记录的所有菜品，方便重新选菜。确定吗？（你的调料库会保留）",
      confirmColor: "#ff6b35",
      success: (res) => {
        if (res.confirm) this.doClearToday();
      }
    });
  },

  async doClearToday() {
    try {
      await request("/clear-orders", { method: "POST", data: { date: this.data.today } });
      wx.removeStorageSync("shopping_" + this.data.today);
      wx.showToast({ title: "已清除，去重新选菜", icon: "none" });
      this.loadShopping(); // 重新生成：菜品清空，但调料库仍在
    } catch (e) {
      wx.showToast({ title: "清除失败", icon: "error" });
    }
  },

  // ===== 家庭共享（房间码） =====

  // 读取本地房间码并拉取共享清单（onShow 调用，与今日清单互不干扰）
  loadShare() {
    const code = wx.getStorageSync("share_code") || "";
    const name = wx.getStorageSync("share_name") || "我";
    this.setData({ shareCode: code, shareName: name });
    if (code) this.loadShareItems();
  },

  async loadShareItems() {
    const code = this.data.shareCode;
    if (!code) return;
    try {
      const res = await request("/share/room/" + code + "/items");
      this.setData({ shareItems: (res.data && res.data.data) || [] });
    } catch (e) { /* 房间失效等异常静默忽略 */ }
  },

  // POST 带重试：Render 免费版实例会冷启动，首次请求常超时（网络层失败）。
  // 仅在「网络层失败」（err 无 statusCode）时重试并等待唤醒；HTTP 错误（如未部署 404）直接抛出。
  async retryPost(url, opts, tries = 2) {
    let lastErr;
    for (let i = 0; i < tries; i++) {
      try {
        return await request(url, Object.assign({ method: "POST" }, opts));
      } catch (e) {
        lastErr = e;
        if (e && e.statusCode) throw e; // HTTP 错误不重试，避免无意义等待
        if (i < tries - 1) await new Promise(r => setTimeout(r, 1200));
      }
    }
    throw lastErr;
  },

  // 创建房间：后端返回 6 位码，存本地即视为加入
  async createRoom() {
    wx.showLoading({ title: "创建中...", mask: true });
    try {
      const res = await this.retryPost("/share/room");
      if (res.data && res.data.code === 200) {
        const code = res.data.data.code;
        wx.setStorageSync("share_code", code);
        this.setData({ shareCode: code, shareJoinInput: "", shareItems: [] });
        wx.hideLoading();
        wx.showToast({ title: "房间码 " + code, icon: "none" });
      } else {
        wx.hideLoading();
        wx.showToast({ title: (res.data && res.data.msg) || "创建失败", icon: "none" });
      }
    } catch (e) {
      wx.hideLoading();
      wx.showToast({ title: "创建失败，稍后重试", icon: "error" });
    }
  },

  onShareJoinInput(e) {
    this.setData({ shareJoinInput: e.detail.value });
  },

  // 加入房间：校验码存在后存本地
  async joinRoom() {
    const code = (this.data.shareJoinInput || "").trim().toUpperCase();
    if (!code) { wx.showToast({ title: "请输入房间码", icon: "none" }); return; }
    wx.showLoading({ title: "加入中...", mask: true });
    try {
      const res = await this.retryPost("/share/room/" + encodeURIComponent(code));
      if (res.data && res.data.code === 200) {
        wx.setStorageSync("share_code", code);
        this.setData({ shareCode: code, shareJoinInput: "" });
        wx.hideLoading();
        wx.showToast({ title: "已加入 " + code, icon: "none" });
        this.loadShareItems();
      } else {
        wx.hideLoading();
        wx.showToast({ title: "房间不存在", icon: "none" });
      }
    } catch (e) {
      wx.hideLoading();
      wx.showToast({ title: "房间不存在", icon: "none" });
    }
  },

  // 向房间添加一道菜（数量默认 1）；失败仅提示，不阻断
  async addShareItem(name, qty) {
    const code = this.data.shareCode;
    if (!code || !name) return;
    try {
      await request("/share/room/" + code + "/items", {
        method: "POST",
        data: { dish_name: name, quantity: qty || 1, added_by: this.data.shareName }
      });
      this.loadShareItems();
    } catch (e) {
      wx.showToast({ title: "添加失败", icon: "error" });
    }
  },

  // 把当前页面的今日菜品（非调料分组）整批加入共享房间
  pushMyList() {
    const dishes = this.data.groups
      .filter(g => !g.isSeasoning)
      .map(g => g.dish);
    if (dishes.length === 0) {
      wx.showToast({ title: "今日还没有菜", icon: "none" });
      return;
    }
    wx.showLoading({ title: "加入中...", mask: true });
    Promise.allSettled(dishes.map(name => this.addShareItem(name, 1)))
      .then(() => {
        wx.hideLoading();
        wx.showToast({ title: "已加入共享", icon: "success" });
      });
  },

  // 从房间移除一道菜
  async removeShareItem(e) {
    const name = e.currentTarget.dataset.name;
    const code = this.data.shareCode;
    if (!code) return;
    try {
      await request("/share/room/" + code + "/items", {
        method: "DELETE",
        data: { dish_name: name }
      });
      this.loadShareItems();
    } catch (err) {
      wx.showToast({ title: "删除失败", icon: "error" });
    }
  },

  // 退出当前房间（仅本地清码，房间与清单保留给其他人）
  leaveRoom() {
    wx.showModal({
      title: "退出共享房间",
      content: "只是退出当前房间，房间与里面的清单仍保留给其他人。确定吗？",
      confirmColor: "#ff6b35",
      success: (res) => {
        if (!res.confirm) return;
        wx.removeStorageSync("share_code");
        this.setData({ shareCode: "", shareItems: [], shareJoinInput: "" });
      }
    });
  },

  goRecord() {
    wx.switchTab({ url: "/pages/index/index" });
  }
});
