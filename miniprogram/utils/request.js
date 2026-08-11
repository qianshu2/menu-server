// utils/request.js —— 统一请求封装
// 解决 4 个页面重复手写 wx.request、缺少超时、错误处理不一致的问题。
// 用法：const { request, getBase } = require("../../utils/request.js");

function getBase() {
  const app = getApp();
  return (app && app.globalData && app.globalData.apiBase) ||
    "https://menu-server-1-1qs7.onrender.com";
}

/**
 * 发起请求，返回 Promise（resolve 值为 wx.request 的 res 对象，含 data 字段）
 * @param {string} url 相对路径，例如 "/menu"
 * @param {object} [opts]
 * @param {string} [opts.method="GET"]
 * @param {object} [opts.data={}]
 * @param {number} [opts.timeout=8000]
 * @param {boolean} [opts.showError=true] 失败时是否自动弹 Toast
 */
function request(url, opts = {}) {
  const {
    method = "GET",
    data = {},
    timeout = 8000,
    showError = true
  } = opts;
  return new Promise((resolve, reject) => {
    wx.request({
      url: getBase() + url,
      method,
      data,
      timeout,
      success: (res) => resolve(res),
      fail: (err) => {
        if (showError) {
          wx.showToast({ title: "网络异常，请稍后重试", icon: "error" });
        }
        reject(err);
      }
    });
  });
}

module.exports = { request, getBase };
