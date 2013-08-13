;(function ($, window, document, undefined) {
    var pluginName = "deferrable",
        defaults = {
        };

    function Plugin(element, options) {
        this.element = element;

        this.options = $.extend({}, defaults, options) ;

        this._defaults = defaults;
        this._name = pluginName;

        this.init();
    }

    $.extend(Plugin.prototype, {
        init: function() {
            this.$element = $(this.element);
            this.url = this.$element.data('url');
            this.params = this.$element.data('params') || [];
            this.listen();
        },
        listen: function() {
            var that = this;
            this.$element.on('reload', function() {
                that.reload();
            });
        },
        reload: function() {
            $.ajax({
                url: this.url,
                data: this.get_params(),
                dataType: 'html',
                success: this.loaded,
                error: this.load_error,
                context: this
            });
        },
        loaded: function(data) {
            var $new_element = $(data);
            this.$element.replaceWith($new_element);

            this.$element = $new_element;
            this.element = this.$element.get(0);

            $.data(this.element, "plugin_" + this._name, this);
            this.listen();

            this.$element.trigger('reloaded');
        },
        load_error: function(jqXHR) {
            alert('Cannot load');
        },
        get_params: function() {
            var params = {};
            for (var i = 0; i < this.params.length; i++) {
                var selector = this.params[i],
                    $node = this.$element.find(selector),
                    node = $node.get(0);

                if (node.type === 'checkbox' || node.type === 'radio') {
                    if (!node.checked) {
                        continue;
                    }
                }

                params[node.name] = $node.val();
            }
            return params;
        },
    });

    $.fn[pluginName] = function (options) {
        return this.each(function () {
            if (!$.data(this, "plugin_" + pluginName)) {
                $.data(this, "plugin_" + pluginName,
                    new Plugin(this, options)
                );
            }
        });
    }

})(jQuery, window, document);
