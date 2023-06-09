/**
 * once the DOM is loaded, 
 */
document.addEventListener('DOMContentLoaded', function() {


});

/**
 * Note: make sure the data is sorted correctly, else it will not show and give a value is null error!
 */


function show_history(security_id, parameter){

    fetch("/data/security_history/" + security_id, {
        method: "POST",
        headers: {"X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value},
        mode: "same-origin",
        body: JSON.stringify({
            "interval":parameter
        })
    })
    .then((response) => {

        if (response.ok){
            response.json().then( data => {
                generate_chart(data)
            })
        } else {
          response.json().then((data) => {
              alert(data.error)
          });
          
        }
    })
    .catch( error => {
        console.log('Error:', error);
    })

	return false
}


function show_tp(security_id, parameter){

    fetch("/data/tp/" + security_id, {
        method: "POST",
        headers: {"X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value},
        mode: "same-origin",
        body: JSON.stringify({
            "view":parameter
        })
    })
    .then((response) => {

        if (response.ok){
            response.json().then( data => {
				console.log(data.tp_data)
                generate_tp_chart(data)
            })
        } else {
          response.json().then((data) => {
              alert(data.error)
          });
          
        }
    })
    .catch( error => {
        console.log('Error:', error);
    })

	return false
}


/**
 * use to generate a table highlighting the technical parameter such as delta from EMA, sigma ...
 * @param {*} security_id 
 * @returns 
 */
function show_ta(security_id){

    fetch("/data/ta/" + security_id, {
        method: "GET",
        mode: "same-origin"
    })
    .then((response) => {

        if (response.ok){
            response.json().then( data => {

				if (document.querySelector("#fa_link") != null){
					document.querySelector("#fa_link").classList.remove("active")
				}
				document.querySelector("#ta_link").classList.add("active")

				div = document.querySelector("#a_data")
				div.innerHTML = ""
				table = document.createElement("table")
				table.classList.add("table", "table-responsive", "table-hover")
				tbody = document.createElement("tbody")
				table.append(tbody)
				for (let key in data) {
					_tr = document.createElement("tr")
					
					_td_l = document.createElement("td")
					_td_l.innerHTML = key
					_tr.append(_td_l)

					_td_r = document.createElement("td")
					if (data[key] >= 0){
						_td_r.classList.add("text-success")
					} else {
						_td_r.classList.add("text-danger")
					}

					_td_r.innerHTML = data[key].toFixed(2)

					_tr.append(_td_r)
					tbody.append(_tr)
				}
				div.append(table)

            })
        } else {
          response.json().then((data) => {
              alert(data.error)
          });
          
        }
    })
    .catch( error => {
        console.log('Error:', error);
    })

	return false
}

/**
 * use to generate a table with the fundamental parameter
 * @param {*} security_id 
 * @returns 
 */
function show_fa(security_id){

    fetch("/data/fa/" + security_id, {
        method: "GET",
        mode: "same-origin"
    })
    .then((response) => {

		if (document.querySelector("#fa_link") != null){
			document.querySelector("#fa_link").classList.add("active")
		}
		document.querySelector("#ta_link").classList.remove("active")

		div = document.querySelector("#a_data")
		div.innerHTML = ""

        if (response.ok){

            response.json().then( data => {
				
				table = document.createElement("table")
				table.classList.add("table", "table-responsive", "table-hover")
				tbody = document.createElement("tbody")
				table.append(tbody)
				for (let key in data) {
					_tr = document.createElement("tr")
					
					_td_l = document.createElement("td")
					_td_l.innerHTML = key
					_tr.append(_td_l)

					_td_r = document.createElement("td")
					if (data[key] === "N/A"){
						_td_r.innerHTML = "N/A"
					} else {
						_td_r.innerHTML = data[key].toFixed(2)
					}
					
					_tr.append(_td_r)
					tbody.append(_tr)
				}
				div.append(table)

            })

        } else {
          response.json().then((data) => {
              //alert(data.error)
			  div.innerHTML = data.error

          });
          
        }
    })
    .catch( error => {
        console.log('Error:', error);
    })

	return false
}


function generate_chart(data){
	var width = 800;
	var height = 450;

	document.querySelector("#chartContainer").innerHTML = ''
	
	var chart = LightweightCharts.createChart(document.querySelector("#chartContainer"), {
		width: width,
		height: height,
		layout: {
			background: {
				type: 'solid',
				color: '#ffffff',
			},
			textColor: 'rgba(3, 103, 166, 0.9)',
		},
		grid: {
			vertLines: {
				color: 'rgba(197, 203, 206, 0.5)',
			},
			horzLines: {
				color: 'rgba(197, 203, 206, 0.5)',
			},
		},
		crosshair: {
			mode: LightweightCharts.CrosshairMode.Normal,
		},
		rightPriceScale: {
			borderColor: 'rgba(197, 203, 206, 0.8)',
		},
		timeScale: {
			borderColor: 'rgba(197, 203, 206, 0.8)',
		},
		
		watermark: {
			visible: true,
			fontSize: 32,
			horzAlign: 'center',
			vertAlign: 'center',
			color: 'rgba(4, 157, 191, 0.3)',
			text: 'wyca-analytics.com',
		},
		
	});
	
	var ema50 = chart.addLineSeries({
		color: '#049DBF',
		lineWidth: 2,
		priceLineVisible: false
	});
	var ema50values = data.ema50
	ema50.setData(ema50values);
	
	var ema20 = chart.addLineSeries({
		color: '#049DBF',
		lineWidth: 1,
		priceLineVisible: false
	});
	var ema20values = data.ema20
	ema20.setData(ema20values);
	
	var bb_lower = chart.addLineSeries({
		color: '#F2A057',
		lineWidth: 0.5,
		priceLineVisible: false
	});
	bb_lower.setData(data.bb_lower);

	var bb_upper = chart.addLineSeries({
		color: '#F2A057',
		lineWidth: 0.5,
		priceLineVisible: false
	});
	bb_upper.setData(data.bb_upper);

	/*
	var macdHistogram = chart.addHistogramSeries({
		color: '#F2A057',
		priceFormat: {
			type: 'volume',
		},
		priceScaleId: 'MACD',
		priceLineVisible: false
	});
	macdHistogram.setData(data.macd);
	chart.priceScale('MACD').applyOptions({
		scaleMargins: {
			top: 0,
			bottom: 0.8,
		},
	});
	*/
	

	if (data.volume.length > 0){
		var volumeSeries = chart.addHistogramSeries({
			color: '#F2A057',
			priceFormat: {
				type: 'volume',
			},
			priceScaleId: 'volume',
		});
		volumeSeries.setData(data.volume);
		chart.priceScale('volume').applyOptions({
			scaleMargins: {
				top: 0.8,
				bottom: 0,
			},
		});
	}

	var candleSeries = chart.addCandlestickSeries({
	  upColor: 'rgba(0, 150, 136, 0.8)',
	  downColor: 'rgba(255,82,82, 0.8)',
	  borderDownColor: '#dc3545',
	  borderUpColor: '#198754',
	  wickDownColor: 'rgba(255, 144, 0, 1)',
	  wickUpColor: 'rgba(255, 144, 0, 1)',
	});
	var candles = data.price
	candleSeries.setData(candles);

	document.querySelector("#nl_daily").classList.remove("active")
	document.querySelector("#nl_weekly").classList.remove("active")
	document.querySelector("#nl_monthly").classList.remove("active")
	document.querySelector("#nl_hurst").classList.remove("active")
	document.querySelector("#nl_sd").classList.remove("active")

	if (data.interval === "d"){
		document.querySelector("#nl_daily").classList.add("active")
	} else if (data.interval === "w"){
		document.querySelector("#nl_weekly").classList.add("active")
	} else {
		document.querySelector("#nl_monthly").classList.add("active")
	}

	
	// Make Chart Responsive with screen resize
	const resizeObserver = new ResizeObserver(entries => {
		if (entries.length === 0 || entries[0].target !== chartContainer) { return }
		const newRect = entries[0].contentRect
		chart.applyOptions({ height: newRect.height, width: newRect.width })
		})
	resizeObserver.observe(chartContainer)
}


function generate_tp_chart(data){
    var width = 800;
    var height = 450;

    document.querySelector("#chartContainer").innerHTML = ''

    var chart = LightweightCharts.createChart(document.querySelector("#chartContainer"), {
	width: width,
  	height: height,
	layout: {
		background: {
            type: 'solid',
            color: '#ffffff',
        },
		textColor: 'rgba(3, 103, 166, 0.9)',
	},
	grid: {
		vertLines: {
			color: 'rgba(197, 203, 206, 0.5)',
		},
		horzLines: {
			color: 'rgba(197, 203, 206, 0.5)',
		},
	},
	crosshair: {
		mode: LightweightCharts.CrosshairMode.Normal,
	},
	rightPriceScale: {
		borderColor: 'rgba(197, 203, 206, 0.8)',
	},
	timeScale: {
		borderColor: 'rgba(197, 203, 206, 0.8)',
	},
	/*
	watermark: {
		visible: true,
		fontSize: 32,
		horzAlign: 'center',
		vertAlign: 'center',
		color: 'rgba(4, 157, 191, 0.3)',
		text: 'wyca-analytics.com',
	},
	*/
    });

    var ema50 = chart.addLineSeries({
        color: '#049DBF',
        lineWidth: 2,
    });
    ema50.setData(data.tp_data);

	reference = 0
	if (data.view === "hurst"){
		reference = 0.5
	} 

    var minPriceLine = {
		price: reference,
		color: '#be1238',
		lineWidth: 2,
		lineStyle: LightweightCharts.LineStyle.Solid,
		axisLabelVisible: true,
		title: "",
	};
    ema50.createPriceLine(minPriceLine);

	document.querySelector("#nl_daily").classList.remove("active")
	document.querySelector("#nl_weekly").classList.remove("active")
	document.querySelector("#nl_monthly").classList.remove("active")
	document.querySelector("#nl_hurst").classList.remove("active")
	document.querySelector("#nl_sd").classList.remove("active")

	if (data.view === "sd"){
		document.querySelector("#nl_sd").classList.add("active")
	} else if (data.view === "hurst"){
		document.querySelector("#nl_hurst").classList.add("active")
	} else {
		
	}

	// Make Chart Responsive with screen resize
	const resizeObserver = new ResizeObserver(entries => {
		if (entries.length === 0 || entries[0].target !== chartContainer) { return }
		const newRect = entries[0].contentRect
		chart.applyOptions({ height: newRect.height, width: newRect.width })
		})
	resizeObserver.observe(chartContainer)
}


function show_max_pain_history(underlying){
	
	fetch("/data/max_pain_history/" + underlying, {
        method: "GET",
        mode: "same-origin"
    })
    .then((response) => {

        if (response.ok){
            response.json().then( data => {
				generate_max_pain_chart(data)

            })
        } else {
          response.json().then((data) => {
              alert(data.error)
          });
          
        }
    })
    .catch( error => {
        console.log('Error:', error);
    })

	return false
}


function show_max_pain_distribution(underlying){
	fetch("/data/max_pain_distribution/" + underlying, {
        method: "GET",
        mode: "same-origin"
    })
    .then((response) => {

        if (response.ok){
            response.json().then( data => {
				document.querySelector("#chartContainer").innerHTML = ''
				document.querySelector("#chartContainer").innerHTML = '<img class="img-fluid" src="data:image/png;base64,' + String(data.distribution.image) + '" alt="Max Pain distribution">'

				document.querySelector("#mp_history").classList.remove("active")
				document.querySelector("#mp_distribution").classList.add("active")
            })
        } else {
          response.json().then((data) => {
              alert(data.error)
          });
          
        }
    })
    .catch( error => {
        console.log('Error:', error);
    })

	return false
}


function generate_max_pain_chart(data){

	document.querySelector("#chartContainer").innerHTML = ''

	document.querySelector("#mp_history").classList.remove("active")
	document.querySelector("#mp_distribution").classList.remove("active")

	const chartOptions = {
		width: 800,
		height: 450,
		layout: {
			background: {
				type: 'solid',
				color: 'white',
			},
			textColor: 'rgba(3, 103, 166, 0.9)',
		},
		grid: {
			vertLines: {
				color: 'rgba(197, 203, 206, 0.5)',
			},
			horzLines: {
				color: 'rgba(197, 203, 206, 0.5)',
			},
		},
		crosshair: {
			mode: LightweightCharts.CrosshairMode.Normal,
		},
		rightPriceScale: {
			borderColor: 'rgba(197, 203, 206, 0.8)',
		},
		timeScale: {
			borderColor: 'rgba(197, 203, 206, 0.8)',
		},
		watermark: {
			visible: true,
			fontSize: 32,
			horzAlign: 'center',
			vertAlign: 'center',
			color: 'rgba(4, 157, 191, 0.3)',
			text: 'wyca-analytics.com',
		},
		
	}

	const chart = LightweightCharts.createChart(document.getElementById("chartContainer"), chartOptions);
	
	// show the max pain over time
	const series = chart.addLineSeries({
		color: '#0378A6',
		lineWidth: 2,
		// disabling built-in price lines
		lastValueVisible: false,
		priceLineVisible: false,
	});
	series.setData(data.max_pain);
	document.querySelector("#mp_history").classList.add("active")

	chart.timeScale().fitContent();

	// Make Chart Responsive with screen resize
	const resizeObserver = new ResizeObserver(entries => {
		if (entries.length === 0 || entries[0].target !== chartContainer) { return }
		const newRect = entries[0].contentRect
		chart.applyOptions({ height: newRect.height, width: newRect.width })
		})
	resizeObserver.observe(chartContainer)
}


function show_corp_bonds(type){

	fetch("/data/corp_bonds_data/" + type, {
        method: "GET",
        mode: "same-origin"
    })
    .then((response) => {

        if (response.ok){
            response.json().then( data => {
				generate_corp_bonds_chart(data)

            })
        } else {
          response.json().then((data) => {
              alert(data.error)
          });
          
        }
    })
    .catch( error => {
        console.log('Error:', error);
    })

	return false
}


function generate_corp_bonds_chart(data){

	var width = 800;
	var height = 450;

	document.querySelector("#chartContainer").innerHTML = ''
	
	var chart = LightweightCharts.createChart(document.querySelector("#chartContainer"), {
		width: width,
		height: height,
		layout: {
			background: {
				type: 'solid',
				color: '#ffffff',
			},
			textColor: 'rgba(3, 103, 166, 0.9)',
		},
		grid: {
			vertLines: {
				color: 'rgba(197, 203, 206, 0.5)',
			},
			horzLines: {
				color: 'rgba(197, 203, 206, 0.5)',
			},
		},
		crosshair: {
			mode: LightweightCharts.CrosshairMode.Normal,
		},
		rightPriceScale: {
			borderColor: 'rgba(197, 203, 206, 0.8)',
		},
		timeScale: {
			borderColor: 'rgba(197, 203, 206, 0.8)',
		},
		
		watermark: {
			visible: true,
			fontSize: 32,
			horzAlign: 'center',
			vertAlign: 'center',
			color: 'rgba(4, 157, 191, 0.3)',
			text: 'wyca-analytics.com',
		},
		
	});

	var ad_line = chart.addLineSeries({
		color: '#049DBF',
		lineWidth: 2,
		priceLineVisible: false
	});
	ad_line.setData(data.ad);
	
	var ema_line = chart.addLineSeries({
		color: '#F2A057',
		lineWidth: 2,
		priceLineVisible: false
	});
	ema_line.setData(data.trend);

	chart.timeScale().fitContent();

	document.querySelector("#cb_hy").classList.remove("active")
	document.querySelector("#cb_ig").classList.remove("active")

	if (data.type === "High Yield"){
		document.querySelector("#cb_hy").classList.add("active")
	} else if (data.type === "Investment Grade"){
		document.querySelector("#cb_ig").classList.add("active")
	}

	// Make Chart Responsive with screen resize
	const resizeObserver = new ResizeObserver(entries => {
		if (entries.length === 0 || entries[0].target !== chartContainer) { return }
		const newRect = entries[0].contentRect
		chart.applyOptions({ height: newRect.height, width: newRect.width })
		})
	resizeObserver.observe(chartContainer)
}


function show_sentiment(source){

	fetch("/data/sentiment", {
        method: "POST",
        headers: {"X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value},
        mode: "same-origin",
        body: JSON.stringify({
			"source": source,
            "size": 400
        })
    })
    .then((response) => {

        if (response.ok){
            response.json().then( data => {
				generate_sentiemnt_chart(data)

            })
        } else {
          response.json().then((data) => {
              alert(data.error)
          });
          
        }
    })
    .catch( error => {
        console.log('Error:', error);
    })

	return false
}


function generate_sentiemnt_chart(data){

	var width = 800;
	var height = 450;

	document.querySelector("#chartContainer").innerHTML = ''
	
	var chart = LightweightCharts.createChart(document.querySelector("#chartContainer"), {
		width: width,
		height: height,
		layout: {
			background: {
				type: 'solid',
				color: '#ffffff',
			},
			textColor: 'rgba(3, 103, 166, 0.9)',
		},
		grid: {
			vertLines: {
				color: 'rgba(197, 203, 206, 0.5)',
			},
			horzLines: {
				color: 'rgba(197, 203, 206, 0.5)',
			},
		},
		crosshair: {
			mode: LightweightCharts.CrosshairMode.Normal,
		},
		rightPriceScale: {
			borderColor: 'rgba(197, 203, 206, 0.8)',
		},
		timeScale: {
			borderColor: 'rgba(197, 203, 206, 0.8)',
		},
		
		watermark: {
			visible: true,
			fontSize: 32,
			horzAlign: 'center',
			vertAlign: 'center',
			color: 'rgba(4, 157, 191, 0.3)',
			text: 'wyca-analytics.com',
		},
		
	});

	document.querySelector("#naaim").classList.remove("active")
	document.querySelector("#aaii").classList.remove("active")
	document.querySelector("#fra").classList.remove("active")
	document.querySelector("#fra-spread").classList.remove("active")

	if (data.source === "NAAIM"){
		var data_set = chart.addLineSeries({
			color: '#F2A057',
			lineWidth: 2,
			priceLineVisible: false
		});
		data_set.setData(data.naaim_exposure);
		document.querySelector("#naaim").classList.add("active")
	}

	if (data.source === "AAII"){
		var bull_data = chart.addLineSeries({
			color: '#F2A057',
			lineWidth: 2,
			priceLineVisible: false
		});
		bull_data.setData(data.aaii_bulls);

		var bear_data = chart.addLineSeries({
			color: '#0378a6',
			lineWidth: 2,
			priceLineVisible: false
		});
		bear_data.setData(data.aaii_bears);

		document.querySelector("#aaii").classList.add("active")
	}

	if (data.source === "FRA"){
		var private_data = chart.addLineSeries({
			color: '#F2A057',
			lineWidth: 2,
			priceLineVisible: false
		});
		private_data.setData(data.private_bears);

		var institutional_data = chart.addLineSeries({
			color: '#0378a6',
			lineWidth: 2,
			priceLineVisible: false
		});
		institutional_data.setData(data.institutional_bears);

		document.querySelector("#fra").classList.add("active")
	}

	if (data.source === "FRA_SPREAD"){
		var data_set = chart.addLineSeries({
			color: '#F2A057',
			lineWidth: 2,
			priceLineVisible: false
		});
		data_set.setData(data.fra_spread);
		var reference = {
			price: 0,
			color: '#be1238',
			lineWidth: 2,
			lineStyle: LightweightCharts.LineStyle.Solid,
			axisLabelVisible: true,
			title: "",
		};
		data_set.createPriceLine(reference);
		document.querySelector("#fra-spread").classList.add("active")
	}
	


	chart.timeScale().fitContent();

	// Make Chart Responsive with screen resize
	const resizeObserver = new ResizeObserver(entries => {
		if (entries.length === 0 || entries[0].target !== chartContainer) { return }
		const newRect = entries[0].contentRect
		chart.applyOptions({ height: newRect.height, width: newRect.width })
		})
	resizeObserver.observe(chartContainer)
}

function show_md(source){

	fetch("/data/md", {
        method: "POST",
        headers: {"X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value},
        mode: "same-origin",
        body: JSON.stringify({
			"source": source,
            "size": 250
        })
    })
    .then((response) => {

        if (response.ok){
            response.json().then( data => {
				generate_md_chart(data)

            })
        } else {
          response.json().then((data) => {
              alert(data.error)
          });
          
        }
    })
    .catch( error => {
        console.log('Error:', error);
    })

	return false
}


function generate_md_chart(data){

	var width = 800;
	var height = 450;

	document.querySelector("#chartContainer").innerHTML = ''
	
	var chart = LightweightCharts.createChart(document.querySelector("#chartContainer"), {
		width: width,
		height: height,
		layout: {
			background: {
				type: 'solid',
				color: '#ffffff',
			},
			textColor: 'rgba(3, 103, 166, 0.9)',
		},
		grid: {
			vertLines: {
				color: 'rgba(197, 203, 206, 0.5)',
			},
			horzLines: {
				color: 'rgba(197, 203, 206, 0.5)',
			},
		},
		crosshair: {
			mode: LightweightCharts.CrosshairMode.Normal,
		},
		rightPriceScale: {
			borderColor: 'rgba(197, 203, 206, 0.8)',
		},
		timeScale: {
			borderColor: 'rgba(197, 203, 206, 0.8)',
		},
		
		watermark: {
			visible: true,
			fontSize: 32,
			horzAlign: 'center',
			vertAlign: 'center',
			color: 'rgba(4, 157, 191, 0.3)',
			text: 'wyca-analytics.com',
		},
		
	});

	document.querySelector("#nyse").classList.remove("active")
	document.querySelector("#nasdaq").classList.remove("active")

	if (data.source === "nyse"){
		document.querySelector("#nyse").classList.add("active")
	} else if (data.source === "nasdaq"){
		document.querySelector("#nasdaq").classList.add("active")
	}
	var data_set = chart.addLineSeries({
		color: '#049DBF',
		lineWidth: 2,
		priceLineVisible: false
	});
	data_set.setData(data.ad_line);
	
	var ema_set = chart.addLineSeries({
		color: '#F2A057',
		lineWidth: 2,
		priceLineVisible: false
	});
	ema_set.setData(data.ema_line)

	const container = document.getElementById('legendContainer');
	container.innerHTML = ''
	const legend = document.createElement('div');
	//legend.style = `position: absolute; left: 12px; top: 12px; z-index: 1; font-size: 14px; font-family: sans-serif; line-height: 18px; font-weight: 300;`;
	legend.style.color = 'black';
	container.appendChild(legend);
	const getLastBar = series => {
		const lastIndex = series.dataByIndex(Math.Infinity, -1);
		return series.dataByIndex(lastIndex);
	};
	const formatPrice = price => (Math.round(price * 100) / 100).toFixed(2);
	const setTooltipHtml = (date, price) => {
		legend.innerHTML = `<div style="margin: 4px 0px;">AD-Line: ${price}</div><div>${date}</div>`;
	};
	
	const updateLegend = param => {
		const validCrosshairPoint = !(
			param === undefined || param.time === undefined || param.point.x < 0 || param.point.y < 0
		);
		const bar = validCrosshairPoint ? param.seriesData.get(data_set) : getLastBar(data_set);
		// time is in the same format that you supplied to the setData method,
		// which in this case is YYYY-MM-DD
		// const time = bar.time;
		const time = new Date(bar.time * 1000).toLocaleDateString("en-US")
		const price = bar.value !== undefined ? bar.value : bar.close;
		const formattedPrice = formatPrice(price);
		setTooltipHtml(time, formattedPrice);
	};
	
	chart.subscribeCrosshairMove(updateLegend);
	updateLegend(undefined);
	
	chart.timeScale().fitContent();

	// Make Chart Responsive with screen resize
	const resizeObserver = new ResizeObserver(entries => {
		if (entries.length === 0 || entries[0].target !== chartContainer) { return }
		const newRect = entries[0].contentRect
		chart.applyOptions({ height: newRect.height, width: newRect.width })
		})
	resizeObserver.observe(chartContainer)
}