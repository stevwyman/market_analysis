/**
 * once the DOM is loaded, 
 */
document.addEventListener('DOMContentLoaded', function() {


});

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
	});
	var ema50values = data.ema50
	ema50.setData(ema50values);
	
	var ema20 = chart.addLineSeries({
		color: 'rgba(4, 111, 232, 1)',
		lineWidth: 1,
	});
	var ema20values = data.ema20
	ema20.setData(ema20values);
	
	if (data.volume.length > 0){
		var volumeSeries = chart.addHistogramSeries({
			color: '#26a69a',
			priceFormat: {
				type: 'volume',
			},
			priceScaleId: '',
		});
		volumeSeries.setData(data.volume);
		chart.priceScale('').applyOptions({
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
	console.log(candles)
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