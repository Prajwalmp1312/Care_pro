const base = require("./app.json").expo;

module.exports = () => {
  const appEnvironment = process.env.EXPO_PUBLIC_APP_ENV || "development";
  const production = appEnvironment === "production";
  const apiUrl = process.env.EXPO_PUBLIC_API_URL || "";
  const allowCleartext = !production && process.env.EXPO_PUBLIC_ALLOW_CLEARTEXT === "true";

  if (production && !apiUrl.startsWith("https://")) {
    throw new Error("Production Care 360 builds require EXPO_PUBLIC_API_URL to use HTTPS.");
  }
  if (production) {
    for (const key of ["EXPO_PUBLIC_PRIVACY_URL", "EXPO_PUBLIC_TERMS_URL", "EXPO_PUBLIC_SUPPORT_URL"]) {
      if (!(process.env[key] || "").startsWith("https://")) {
        throw new Error(`Production Care 360 builds require ${key} to use HTTPS.`);
      }
    }
  }

  return {
    ...base,
    android: {
      ...base.android,
      usesCleartextTraffic: allowCleartext,
    },
    ios: {
      ...base.ios,
      infoPlist: {
        ...(base.ios?.infoPlist || {}),
        NSAppTransportSecurity: {
          NSAllowsArbitraryLoads: false,
          NSAllowsLocalNetworking: !production,
        },
      },
    },
    extra: {
      appEnvironment,
    },
  };
};
