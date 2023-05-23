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
}


function show_ta(security_id){

    fetch("/data/ta/" + security_id, {
        method: "GET",
        headers: {"X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value},
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
}


function show_fa(security_id){

    fetch("/data/fa/" + security_id, {
        method: "GET",
        headers: {"X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value},
        mode: "same-origin"
    })
    .then((response) => {

        if (response.ok){
            response.json().then( data => {
				
				if (document.querySelector("#fa_link") != null){
					document.querySelector("#fa_link").classList.add("active")
				}
				document.querySelector("#ta_link").classList.remove("active")

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
              alert(data.error)
          });
          
        }
    })
    .catch( error => {
        console.log('Error:', error);
    })
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
			textColor: 'rgba(47, 79, 79, 0.9)',
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
			color: 'rgba(171, 71, 188, 0.3)',
			text: 'wyca-analytics.com',
		},
		*/
	});
	
	var ema50 = chart.addLineSeries({
		color: 'rgba(4, 111, 232, 1)',
		lineWidth: 2,
		priceLineVisible: false
	});
	var ema50values = data.ema50
	ema50.setData(ema50values);
	
	var ema20 = chart.addLineSeries({
		color: 'rgba(4, 111, 232, 1)',
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
		textColor: 'rgba(47, 79, 79, 0.9)',
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
		color: 'rgba(171, 71, 188, 0.3)',
		text: 'wyca-analytics.com',
	},
	*/
    });

    var ema50 = chart.addLineSeries({
        color: 'rgba(4, 111, 232, 1)',
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


function show_max_pain(underlying){
	fetch("/data/max_pain/" + underlying, {
        method: "GET",
        headers: {"X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value},
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
}


function generate_max_pain_chart(data){

	const chartOptions = {
		width: 800,
		height: 450,
		layout: {
			background: {
				type: 'solid',
				color: 'white',
			},
			textColor: 'rgba(47, 79, 79, 0.9)',
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
			color: 'rgba(171, 71, 188, 0.3)',
			text: 'wyca-analytics.com',
		},
		*/
	}

	const chart = LightweightCharts.createChart(document.getElementById("chartContainer"), chartOptions);
	
	const series = chart.addLineSeries({
		color: '#2962FF',
		lineWidth: 2,
		// disabling built-in price lines
		lastValueVisible: false,
		priceLineVisible: false,
	});
	series.setData(data.max_pain);

	chart.timeScale().fitContent();

	// Make Chart Responsive with screen resize
	const resizeObserver = new ResizeObserver(entries => {
		if (entries.length === 0 || entries[0].target !== chartContainer) { return }
		const newRect = entries[0].contentRect
		chart.applyOptions({ height: newRect.height, width: newRect.width })
		})
	resizeObserver.observe(chartContainer)
}
