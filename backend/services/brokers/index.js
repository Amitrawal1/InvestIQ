// Registry of supported brokers (adapters share the same interface)
const upstox = require("./upstox");
const zerodha = require("./zerodha");

const BROKERS = { upstox, zerodha };
const BROKER_NAMES = Object.keys(BROKERS);

const getBroker = (name) => BROKERS[String(name || "").toLowerCase()] || null;

module.exports = { BROKERS, BROKER_NAMES, getBroker };
