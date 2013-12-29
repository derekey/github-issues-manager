var IssuesByDayGraph = {

    klass: 'issues-by-day',

    tooltip: '<div style="text-align:center; font-weight: bold; text-decoration: underline; margin-bottom: 3px;">%(date)s</div>'
           + '<div><strong>Issues: </strong>%(nb_issues)s</div>'
           + '<div><strong>Pull requests: </strong>%(nb_prs)s</div>'
           + '<div><Strong>Total: </strong>%(nb_total)s</div>',

    options: {
        type: 'bar',
        stackedBarColor: ['#E5E5E5', '#D5D5D5'],
        highlightColor: '#F0F0F0',
    },

    create_node: (function IssuesByDayGraph_create_node() {
        return $('<span class="sparkline-graph" />').addClass(IssuesByDayGraph.klass);
    }), // create_node

    make_graph: (function IssuesByDayGraph_make_graph($graph_node, data) {
        $graph_node.sparkline(data.graph_data, $.extend({}, IssuesByDayGraph.options, {
            height: data.max_height,
            tooltipFormatter: function(sparkline, options, fields) {
                return IssuesByDayGraph.tooltip
                    .replace('%(date)s', data.dates[fields[0].offset])
                    .replace('%(nb_issues)s', fields[1].value)
                    .replace('%(nb_prs)s', fields[0].value)
                    .replace('%(nb_total)s', fields[0].value + fields[1].value);
            }
        }));
    }), // make_graph

    fetch_and_make_graph: (function IssuesByDayGraph_fetch_and_make_graph(repo_id, height, $parent_node) {
        var url = graph_data_urls.issues_by_day.replace('99999', repo_id) + '?height=' + height,
            $graph_node = IssuesByDayGraph.create_node();
        $parent_node.append($graph_node);
        $.get(url, function(data) {
            IssuesByDayGraph.make_graph($graph_node, data);
        });
    }) // fetch_and_make_graph

}; // IssuesByDayGraph
