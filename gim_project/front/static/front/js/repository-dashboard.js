$().ready(function() {

    var $document = $(document);

    var DashboardWidget = Class.$extend({
        __init__: function(id, change_selector) {
            this.id = id;
            this.selector = '#' + this.id;
            this.change_selector = change_selector;
            this.refresh();
            this.init_events();
        }, // __init__

        set_node: function() {
            this.$node = $(this.selector);
        }, // set_node

        refresh: function() {
            this.set_node();
            if (!this.$node.length) { return; }
            this.prepare_content();
        }, // refresh

        prepare_content: function() {

        }, // prepare_content

        init_events: function() {
            var widget = this;
            $document.on('reloaded', this.selector, function() {
                widget.refresh();
            });
            if (this.change_selector) {

                $document.on('change', this.change_selector, function() {
                    $(this).closest(widget.selector).trigger('reload');
                });
            }
        }

    }); // DashboardWidget

    var MilestonesDashboardWidget = DashboardWidget.$extend({
        __init__ : function() {
            this.$super("milestones", 'input[name=show-closed-milestones], input[name=show-empty-milestones]');
        }, // __init__
        init_events: function() {
            this.$super();
            $document.on('click', '#milestones a[data-toggle=collapse]', function(ev) {
                ev.preventDefault();
            });
        } // init_events
    }); // MilestonesDashboardWidget

    var LabelsDashboardWidget = DashboardWidget.$extend({
        __init__ : function() {
            this.$super("labels", 'input[name=show-empty-labels]');
        } // __init__
    }); // LabelsDashboardWidget

    MilestonesDashboardWidget();
    LabelsDashboardWidget();

    var $body = $('body');
    IssuesByDayGraph.fetch_and_make_graph($body.data('repository-id'), 40, $body.find('main > .row-header .area-top'));
});
