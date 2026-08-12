App({
  globalData: {
    // 线上地址（开发时可切回 http://127.0.0.1:5000）
    apiBase: "https://menu-server-1-1qs7.onrender.com"
  },

  onLaunch() {
    // 隐私合规：剪贴板等隐私接口需用户授权后调用。
    // 基础库 < 2.32.3 不支持隐私接口，直接跳过。
    if (typeof wx.requirePrivacyAuthorize !== "function") return;
    wx.getPrivacySetting({
      success: (res) => {
        if (res.needAuthorization) {
          // 弹出官方隐私授权窗（含《微信小程序隐私保护指引》链接）
          wx.requirePrivacyAuthorize({
            success: () => {},
            fail: () => {}
          });
        }
      }
    });
  }
});
