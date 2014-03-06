(function($, window, document, undefined) {
	$.fn.quicksearch = function (target, opt) {

		var timeout, cache, rowcache, jq_results, val = '', e = this, options = $.extend({
			delay: 100,
			selector: null,
			selector_data: null,
			stripeRows: null,
			loader: null,
			noResults: '',
			matchedResultsCount: 0,
			bind: 'keyup',
			fuzzy: true,
			onBefore: function () {
				return;
			},
			onAfter: function () {
				return;
			},
			show: function () {
				this.style.display = "";
			},
			hide: function () {
				this.style.display = "none";
			},
			prepareQuery: function (val, split) {
				var result = val.toLowerCase();
				if (split) { result = result.split(' '); }
				return result;
			},
			testQuery: function (query, txt, _row) {
				for (var i = 0; i < query.length; i += 1) {
					if (txt.indexOf(query[i]) === -1) {
						return false;
					}
				}
				return true;
			},
			testQueryFuzzy: function (query, txt, _row) {
			    var last = -1;
			    for (var i = 0; i < query.length; i++) {
			        last = txt.indexOf(query[i], last+1);
			        if (last == -1) { return false; }
			    }
			    return true;
			}
		}, opt);

		this.go = function () {

			var i = 0,
				numMatchedRows = 0,
				noresults = true,
				query = options.prepareQuery(val, !options.fuzzy),
				val_empty = (val.replace(' ', '').length === 0),
				method = options.fuzzy ? options.testQueryFuzzy : options.testQuery;

			for (var i = 0, len = rowcache.length; i < len; i++) {
				if (val_empty || method(query, cache[i], rowcache[i])) {
					options.show.apply(rowcache[i]);
					noresults = false;
					numMatchedRows++;
				} else {
					options.hide.apply(rowcache[i]);
				}
			}

			if (noresults) {
				this.results(false);
			} else {
				this.results(true);
				this.stripe();
			}

			this.matchedResultsCount = numMatchedRows;
			this.loader(false);
			options.onAfter();

			return this;
		};

		this.search = function (submittedVal) {
			val = submittedVal;
			e.trigger_search();
		};

		this.currentMatchedResults = function() {
			return this.matchedResultsCount;
		};

		this.stripe = function () {

			if (typeof options.stripeRows === "object" && options.stripeRows !== null)
			{
				var joined = options.stripeRows.join(' ');
				var stripeRows_length = options.stripeRows.length;

				jq_results.not(':hidden').each(function (i) {
					$(this).removeClass(joined).addClass(options.stripeRows[i % stripeRows_length]);
				});
			}

			return this;
		};


		this.strip = function(input) {
			return $.trim(input.toLowerCase());
		};

		this.strip_html = function (input) {
			var output = input.replace(new RegExp('<[^<]+\>', 'g'), "");
			return e.strip(output);
		};

		this.results = function (bool) {
			if (typeof options.noResults === "string" && options.noResults !== "") {
				if (bool) {
					$(options.noResults).hide();
				} else {
					$(options.noResults).show();
				}
			}
			return this;
		};

		this.loader = function (bool) {
			if (typeof options.loader === "string" && options.loader !== "") {
				 (bool) ? $(options.loader).show() : $(options.loader).hide();
			}
			return this;
		};

		this.cache = function () {

			jq_results = $(target);

			if (typeof options.noResults === "string" && options.noResults !== "") {
				jq_results = jq_results.not(options.noResults);
			}

			var t = (typeof options.selector === "string") ? jq_results.find(options.selector) : $(target).not(options.noResults);
			cache = t.map(function () {
				if (options.selector_data) {
					return e.strip(this.getAttribute('data-' + options.selector_data) || $(this).data(options.selector_data));
				} else {
					return e.strip_html(this.innerHTML);
				}
			});

			rowcache = jq_results.map(function () {
				return this;
			});

			val = val || this.val() || "";

			return this.go();
		};

		this.trigger_search = function () {
			this.loader(true);
			options.onBefore();

			window.clearTimeout(timeout);
			timeout = window.setTimeout(function () {
				e.go();
			}, options.delay);

			return this;
		};

		this.cache();
		this.results(true);
		this.stripe();
		this.loader(false);

		return this.each(function () {

			$(this).on(options.bind, function () {

				val = $(this).val();
				e.trigger_search();
			});
		});

	};

}(jQuery, this, document));
