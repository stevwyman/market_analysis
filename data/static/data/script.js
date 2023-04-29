/**
 * once the DOM is loaded, 
 */
document.addEventListener('DOMContentLoaded', function() {


});

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
                tp_data = JSON.parse(data.tp_data)
                generate_tp_chart(tp_data)
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


function generate_tp_chart(data){
    var width = 720;
    var height = 450;

    document.querySelector("#tp_chart").innerHTML = ''

    var chart = LightweightCharts.createChart(document.querySelector("#tp_chart"), {
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
    var ema50values = data
    ema50.setData(ema50values);

    var minPriceLine = {
		price: 0,
		color: '#be1238',
		lineWidth: 2,
		lineStyle: LightweightCharts.LineStyle.Solid,
		axisLabelVisible: true,
		title: '0',
	};
    ema50.createPriceLine(minPriceLine);
}