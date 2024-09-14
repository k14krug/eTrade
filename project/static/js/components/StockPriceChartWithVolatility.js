// File: project/static/js/components/StockPriceChartWithVolatility.js

(function(React, Recharts) {
  const { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } = Recharts;

  function StockPriceChartWithVolatility({ data }) {
    console.log('Received data:', data);

    return React.createElement(ResponsiveContainer, { width: "100%", height: 400 },
      React.createElement(LineChart, { data: data },
        React.createElement(CartesianGrid, { strokeDasharray: "3 3" }),
        React.createElement(XAxis, { dataKey: "date" }),
        React.createElement(YAxis, { domain: ['auto', 'auto'] }),
        React.createElement(Tooltip),
        React.createElement(Line, { type: "monotone", dataKey: "price", stroke: "#8884d8", dot: false })
      )
    );
  }

  window.StockPriceChartWithVolatility = StockPriceChartWithVolatility;
})(window.React, window.Recharts);