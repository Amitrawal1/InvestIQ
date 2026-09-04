import { r as __toESM } from "./rolldown-runtime-DC62tzP2.js";
import { t as require_react } from "./react.js";
import { t as require_jsx_runtime } from "./jsx-runtime-BdjH9Isp.js";
import { C as RadarController, E as ScatterController, S as PolarAreaController, b as PieController, c as BubbleController, g as LineController, i as BarController, p as DoughnutController, u as Chart$1 } from "./chart-B_IE3wKg.js";
//#region node_modules/react-chartjs-2/dist/index.js
var import_jsx_runtime = require_jsx_runtime();
var import_react = /* @__PURE__ */ __toESM(require_react(), 1);
var defaultDatasetIdKey = "label";
function reforwardRef(ref, value) {
	if (typeof ref === "function") ref(value);
	else if (ref) ref.current = value;
}
function setOptions(chart, nextOptions) {
	const options = chart.options;
	if (options && nextOptions) Object.assign(options, nextOptions);
}
function setLabels(currentData, nextLabels) {
	currentData.labels = nextLabels;
}
function setDatasets(currentData, nextDatasets, datasetIdKey = defaultDatasetIdKey) {
	const addedDatasets = [];
	currentData.datasets = nextDatasets.map((nextDataset) => {
		const currentDataset = currentData.datasets.find((dataset) => dataset[datasetIdKey] === nextDataset[datasetIdKey]);
		if (!currentDataset || !nextDataset.data || addedDatasets.includes(currentDataset)) return { ...nextDataset };
		addedDatasets.push(currentDataset);
		Object.assign(currentDataset, nextDataset);
		return currentDataset;
	});
}
function cloneData(data, datasetIdKey = defaultDatasetIdKey) {
	const nextData = {
		labels: [],
		datasets: []
	};
	setLabels(nextData, data.labels);
	setDatasets(nextData, data.datasets, datasetIdKey);
	return nextData;
}
/**
* Get dataset from mouse click event
* @param chart - Chart.js instance
* @param event - Mouse click event
* @returns Dataset
*/ function getDatasetAtEvent(chart, event) {
	return chart.getElementsAtEventForMode(event.nativeEvent, "dataset", { intersect: true }, false);
}
/**
* Get single dataset element from mouse click event
* @param chart - Chart.js instance
* @param event - Mouse click event
* @returns Dataset
*/ function getElementAtEvent(chart, event) {
	return chart.getElementsAtEventForMode(event.nativeEvent, "nearest", { intersect: true }, false);
}
/**
* Get all dataset elements from mouse click event
* @param chart - Chart.js instance
* @param event - Mouse click event
* @returns Dataset
*/ function getElementsAtEvent(chart, event) {
	return chart.getElementsAtEventForMode(event.nativeEvent, "index", { intersect: true }, false);
}
function ChartComponent(props, ref) {
	const { height = 150, width = 300, redraw = false, datasetIdKey, type, data, options, plugins = [], fallbackContent, updateMode, ...canvasProps } = props;
	const canvasRef = (0, import_react.useRef)(null);
	const chartRef = (0, import_react.useRef)(null);
	const renderChart = () => {
		if (!canvasRef.current) return;
		chartRef.current = new Chart$1(canvasRef.current, {
			type,
			data: cloneData(data, datasetIdKey),
			options: options && { ...options },
			plugins
		});
		reforwardRef(ref, chartRef.current);
	};
	const destroyChart = () => {
		reforwardRef(ref, null);
		if (chartRef.current) {
			chartRef.current.destroy();
			chartRef.current = null;
		}
	};
	(0, import_react.useEffect)(() => {
		if (!redraw && chartRef.current && options) setOptions(chartRef.current, options);
	}, [redraw, options]);
	(0, import_react.useEffect)(() => {
		if (!redraw && chartRef.current) setLabels(chartRef.current.config.data, data.labels);
	}, [redraw, data.labels]);
	(0, import_react.useEffect)(() => {
		if (!redraw && chartRef.current && data.datasets) setDatasets(chartRef.current.config.data, data.datasets, datasetIdKey);
	}, [redraw, data.datasets]);
	(0, import_react.useEffect)(() => {
		if (!chartRef.current) return;
		if (redraw) {
			destroyChart();
			setTimeout(renderChart);
		} else chartRef.current.update(updateMode);
	}, [
		redraw,
		options,
		data.labels,
		data.datasets,
		updateMode
	]);
	(0, import_react.useEffect)(() => {
		if (!chartRef.current) return;
		destroyChart();
		setTimeout(renderChart);
	}, [type]);
	(0, import_react.useEffect)(() => {
		renderChart();
		return () => destroyChart();
	}, []);
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)("canvas", {
		ref: canvasRef,
		role: "img",
		height,
		width,
		...canvasProps,
		children: fallbackContent
	});
}
var Chart = /*#__PURE__*/ (0, import_react.forwardRef)(ChartComponent);
function createTypedChart(type, registerables) {
	Chart$1.register(registerables);
	return /*#__PURE__*/ (0, import_react.forwardRef)((props, ref) => /*#__PURE__*/ (0, import_jsx_runtime.jsx)(Chart, {
		...props,
		ref,
		type
	}));
}
var Line = /* #__PURE__ */ createTypedChart("line", LineController);
var Bar = /* #__PURE__ */ createTypedChart("bar", BarController);
var Radar = /* #__PURE__ */ createTypedChart("radar", RadarController);
var Doughnut = /* #__PURE__ */ createTypedChart("doughnut", DoughnutController);
var PolarArea = /* #__PURE__ */ createTypedChart("polarArea", PolarAreaController);
var Bubble = /* #__PURE__ */ createTypedChart("bubble", BubbleController);
var Pie = /* #__PURE__ */ createTypedChart("pie", PieController);
var Scatter = /* #__PURE__ */ createTypedChart("scatter", ScatterController);
//#endregion
export { Bar, Bubble, Chart, Doughnut, Line, Pie, PolarArea, Radar, Scatter, getDatasetAtEvent, getElementAtEvent, getElementsAtEvent };
