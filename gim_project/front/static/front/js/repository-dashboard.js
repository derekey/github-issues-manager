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

        prepare_content: function() {
            this.$node.find('input[name="show-closed-milestones"]').iButton({
                labelOn: 'With closed',
                labelOff: 'Without closed',
                className: 'no-text-transform small',
                handleWidth: 24
            });
            this.$node.find('input[name="show-empty-milestones"]').iButton({
                labelOn: 'With empty',
                labelOff: 'Without empty',
                className: 'no-text-transform small',
                handleWidth: 24
            });
        } // prepare_content

    }); // MilestonesDashboardWidget

    var LabelsDashboardWidget = DashboardWidget.$extend({
        __init__ : function() {
            this.$super("labels", 'input[name=show-empty-labels]');
        }, // __init__

        prepare_content: function() {
            this.$node.find('input[name="show-empty-labels"]').iButton({
                labelOn: 'With empty',
                labelOff: 'Without empty',
                className: 'no-text-transform small',
                handleWidth: 24
            });
        } // prepare_content

    }); // LabelsDashboardWidget

    MilestonesDashboardWidget();
    LabelsDashboardWidget();

});
