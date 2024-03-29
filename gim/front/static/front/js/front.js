$().ready(function() {
    function GetVendorAttribute(prefixedAttributes) {
       var tmp = document.createElement("div");
       var result = "";
       for (var i = 0; i < prefixedAttributes.length; ++i) {
           if (typeof tmp.style[prefixedAttributes[i]] != 'undefined') {
              return prefixedAttributes[i];
           }
       }
       return null;
    }

    var $document = $(document),
        $body = $('body'),
        main_repository = $body.data('repository')
        transform_attribute = GetVendorAttribute(["transform", "msTransform", "MozTransform", "WebkitTransform", "OTransform"]);


    var Ev = {
        stop_event_decorate: (function stop_event_decorate(callback) {
            /* Return a function to use as a callback for an event
               Call the callback and if it returns false (strictly), the
               event propagation is stopped
            */
            var decorator = function(e) {
                if (e.isPropagationStopped()) { return false; }
                if (callback.bind(this)(e) === false) {
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }
            };
            return decorator;
        }), // stop_event_decorate

        cancel: (function cancel(e) {
            /* A simple callback to use to simply cancel an event
            */
            e.preventDefault();
            e.stopPropagation();
            return false;
        }), // cancel

        stop_event_decorate_dropdown: (function stop_event_decorate_dropdown(callback, klass) {
            /* Return a function to use as a callback for clicks on dropdown items
               It will close the dropwdown before calling the callback, and will
               return false to tell to the main decorator to stop the event
            */
            if (typeof klass === 'undefined') { klass = '.dropdown'; }
            var decorator = function(e) {
                var dropdown = $(e.target).closest(klass);
                if (dropdown.hasClass('open')) {
                    dropdown.children('.dropdown-toggle').dropdown('toggle');
                }
                return callback.bind(this)(e);
            };
            return Ev.stop_event_decorate(decorator);
        }), // stop_event_decorate_dropdown

        key_decorate: (function key_decorate(callback) {
            /* Return a function to use as a callback for a jwery event
               Will cancel the call of the callback if the focus is actually on an
               input element.
               If not, the callback is called, and if it returns true
               (strictly), the event propagation is stopped
            */
            var decorator = function(e) {
                if ($(e.target).is(':input')) { return; }
                return callback(e);
            };
            return Ev.stop_event_decorate(decorator);
        }), // key_decorate

        charcode: (function charcode(charcode, callback) {
            /* Return a function to use as a callback for a key* event
               The callback will only be called if the charcode is the given one.
               Can be used with key_decorate
            */
            var decorator = function(e) {
                if (e.charCode != charcode) { return; }
                return callback(e);
            };
            return Ev.stop_event_decorate(decorator);
        }), // charcode

        set_focus: (function set_focus($node, delay) {
            /* Event handler to set the focus on the given node.
            */
            return function(ev) {
                if (delay) {
                    setTimeout(Ev.set_focus($node), delay);
                } else {
                    $node.focus();
                }
            }
        }) // set_focus
    };


    // globally manage escape key to close modal
    $document.on('keyup.dismiss.modal', Ev.key_decorate(function(ev) {
        ev.which == 27 && $('.modal.in').modal('hide');
    }));


    var IssuesListIssue = (function IssuesListIssue__constructor (node, issues_list_group) {
        this.group = issues_list_group;

        this.node = node;
        this.node.IssuesListIssue = this;
        this.$node = $(node);
        this.$link = this.$node.find(IssuesListIssue.link_selector);

        this.set_issue_ident({
            number: this.$node.data('number'),
            repository: this.$node.data('repository')
        });
    }); // IssuesListIssue__constructor

    IssuesListIssue.selector = '.issue-item';
    IssuesListIssue.link_selector = '.issue-link';

    IssuesListIssue.prototype.set_issue_ident = (function IssuesListIssue__set_issue_ident (issue_ident) {
        this.issue_ident = issue_ident;
        this.number = issue_ident.number;
        this.repository = issue_ident.repository;
    }); // IssuesListIssue__set_issue_ident

    IssuesListIssue.on_issue_node_event = (function IssuesListIssue_on_issue_node_event (group_method, stop) {
        var decorator = function(e) {
            // ignore filter links
            if (e.target.nodeName.toUpperCase() == 'A' && e.target.className.indexOf('issue-link') == -1 || e.target.parentNode.nodeName.toUpperCase() == 'A') { return; }

            var issue_node = $(e.target).closest(IssuesListIssue.selector);
            if (!issue_node.length || !issue_node[0].IssuesListIssue) { return; }
            return issue_node[0].IssuesListIssue[group_method]();
        };
        return stop ? Ev.stop_event_decorate(decorator) : decorator;
    }); // IssuesListIssue_on_issue_node_event

    IssuesListIssue.init_events = (function IssuesListIssue_init_events () {
        $document.on('click', IssuesListIssue.selector, IssuesListIssue.on_issue_node_event('on_click', true));
    });

    IssuesListIssue.prototype.on_click = (function IssuesListIssue__on_click (e) {
        this.set_current(true);
        return false; // stop event propagation
    }); // IssuesListIssue__on_click

    IssuesListIssue.prototype.unset_current = (function IssuesListIssue__unset_current () {
        this.group.current_issue = null;
        this.$node.removeClass('active');
    }); // IssuesListIssue__unset_current

    IssuesListIssue.prototype.set_current = (function IssuesListIssue__set_current (propagate, force_load, no_loading) {
        this.get_html_and_display(null, null, force_load, no_loading);
        if (!this.group.no_visible_issues) {
            if (propagate) {
                this.group.list.set_current();
                this.group.set_current();
            }
            if (this.group.current_issue) {
                this.group.current_issue.unset_current();
            }
            this.group.current_issue = this;
            this.group.unset_active();
            this.$node.addClass('active');
            var issue = this;
            if (this.group.collapsed) {
                this.group.open(false, function() { issue.$link.focus(); });
            } else {
                this.$link.focus();
            }
        }
    }); // IssuesListIssue__set_current

    IssuesListIssue.prototype.get_html_and_display = (function IssuesListIssue__get_html_and_display (url, force_popup, force_load, no_loading) {
        var container = IssueDetail.get_container_waiting_for_issue(this.issue_ident, force_popup, force_load);
        if (!container) {
            return;
        }
        var is_popup = !!(force_popup || container.$window);
        if (!url) { url = this.$link.attr('href'); }
        if (!no_loading) {
            IssueDetail.set_container_loading(container);
        } else {
            IssueDetail.unset_issue_waypoints(container.$node);
        }
        if (is_popup) {
            // open the popup with its loading spinner
            container.$window.modal("show");
        }
        $.ajax({
            url: url,
            success: is_popup ? this.display_html_in_popup : this.display_html,
            error: is_popup ? this.error_getting_html_in_popup: this.error_getting_html,
            context: this
        });
    }); // IssuesListIssue__get_html_and_display

    IssuesListIssue.prototype.display_html = (function IssuesListIssue__display_html (html) {
        IssueDetail.display_issue(html, this.issue_ident, false);
    }); // IssuesListIssue__display_html

    IssuesListIssue.prototype.display_html_in_popup = (function IssuesListIssue__display_html_in_popup (html) {
        IssueDetail.display_issue(html, this.issue_ident, true);
    }); // IssuesListIssue__display_html_in_popup

    IssuesListIssue.prototype.error_getting_html = (function IssuesListIssue__error_getting_html (jqXHR) {
        IssueDetail.clear_container('error ' + jqXHR.status, false);
    }); // IssuesListIssue__error_getting_html

    IssuesListIssue.prototype.error_getting_html_in_popup = (function IssuesListIssue__error_getting_html_in_popup (jqXHR) {
        alert('error ' + jqXHR.status);
    }); // IssuesListIssue__error_getting_html_in_popup

    IssuesListIssue.open_issue = (function IssuesListIssue_open_issue (issue_ident, force_popup, force_load, no_loading) {
        var issue = IssuesList.get_issue_by_ident(issue_ident);
        if (issue) {
            if (force_popup) {
                issue.get_html_and_display(null, true, force_load, no_loading);
            } else {
                issue.set_current(true, force_load, no_loading);
            }
        } else {
            var url = IssueDetail.get_url_for_ident(issue_ident);
            issue = new IssuesListIssue({}, null);
            issue.set_issue_ident(issue_ident);
            issue.get_html_and_display(url, force_popup, force_load, no_loading);
        }
    }); // IssuesListIssue_open_issue

    var IssuesListGroup = (function IssuesListGroup__constructor (node, issues_list) {
        this.list = issues_list;

        this.node = node;
        this.node.IssuesListGroup = this;
        this.$node = $(node);
        this.$link = this.$node.find(IssuesListGroup.link_selector);
        this.$issues_node = this.$node.find(IssuesListGroup.issues_list_selector);
        this.$count_node = this.$node.find('.issues-count');

        this.collapsable = this.$issues_node.hasClass('collapse');
        this.collapsed = this.collapsable && !this.$issues_node.hasClass('in');

        var group = this;
        this.issues = $.map(this.$node.find(IssuesListIssue.selector),
                    function(node) { return new IssuesListIssue(node, group); });
        this.filtered_issues = this.issues;
        this.current_issue = null;

        this.no_visible_issues = this.filtered_issues.length === 0;
    }); // IssuesListGroup__constructor

    IssuesListGroup.selector = '.issues-group';
    IssuesListGroup.link_selector = '.box-header';
    IssuesListGroup.issues_list_selector = '.issues-group-issues';

    IssuesListGroup.prototype.unset_active = (function IssuesListGroup__unset_active () {
        this.$node.removeClass('active');
    }); // IssuesListGroup__unset_active

    IssuesListGroup.prototype.set_active = (function IssuesListGroup__set_active () {
        if (this.current_issue) {
            this.current_issue.unset_current();
        }
        IssueDetail.clear_container();
        this.$node.addClass('active');
        this.$link.focus();
    }); // IssuesListGroup__set_active

    IssuesListGroup.prototype.unset_current = (function IssuesListGroup__unset_current () {
        this.unset_active();
        if (this.current_issue) {
            this.current_issue.unset_current();
        }
        this.list.current_group = null;
    }); // IssuesListGroup__set_current

    IssuesListGroup.prototype.set_current = (function IssuesListGroup__set_current (active) {
        if (this.list.current_group) {
            this.list.current_group.unset_current();
        }
        this.list.current_group = this;
        if (active) {
            this.set_active();
        }
    }); // IssuesListGroup__set_current

    IssuesListGroup.prototype.open = (function IssuesListGroup__open (set_active, on_shown_callback) {
        if (!this.collapsable || !this.collapsed || this.no_visible_issues) { return ; }
        if (set_active) { this.set_active(); }
        if (on_shown_callback) {
            var group = this,
                on_shown = function() {
                    group.$issues_node.off('shown.collapse', on_shown);
                    on_shown_callback();
                };
            this.$issues_node.on('shown.collapse', on_shown);
        }
        this.$issues_node.collapse('show');
        return false; // stop event propagation
    }); // IssuesListGroup__open

    IssuesListGroup.prototype.close = (function IssuesListGroup__close (set_active) {
        if (!this.collapsable || this.collapsed || this.no_visible_issues) { return; }
        if (set_active) { this.set_active(); }
        this.$issues_node.collapse('hide');
        return false; // stop event propagation
    }); // IssuesListGroup__close

    IssuesListGroup.prototype.toggle = (function IssuesListGroup__toggle (set_active) {
        if (!this.collapsable || this.no_visible_issues) { return; }
        return this.collapsed ? this.open(set_active) : this.close(set_active);
    }); // IssuesListGroup__toggle

    IssuesListGroup.on_group_node_event = (function IssuesListGroup_on_group_node_event (group_method, stop) {
        var decorator = function(e) {
            var group_node = $(e.target).closest(IssuesListGroup.selector);
            if (!group_node.length || !group_node[0].IssuesListGroup) { return; }
            return group_node[0].IssuesListGroup[group_method]();
        };
        return stop ? Ev.stop_event_decorate(decorator): decorator;
    }); // IssuesListGroup_on_group_node_event

    IssuesListGroup.on_current_group_key_event = (function IssuesListGroup_on_current_group_key_event (group_method, param) {
        var decorator = function(e) {
            if (!IssuesList.current) { return; }
            if (!IssuesList.current.current_group) { return; }
            return IssuesList.current.current_group[group_method](param);
        };
        return Ev.key_decorate(decorator);
    }); // IssuesListGroup_on_current_group_key_event

    IssuesListGroup.init_events = (function IssuesListGroup_init_events () {
        $document.on('click', IssuesListGroup.link_selector, IssuesListGroup.on_group_node_event('on_click', true));
        $document.on('show.collapse', IssuesListGroup.issues_list_selector, IssuesListGroup.on_group_node_event('on_show'));
        $document.on('hide.collapse', IssuesListGroup.issues_list_selector, IssuesListGroup.on_group_node_event('on_hide'));
        jwerty.key('o/→', IssuesListGroup.on_current_group_key_event('open', true));
        jwerty.key('c/←', IssuesListGroup.on_current_group_key_event('close', true));
        jwerty.key('t', IssuesListGroup.on_current_group_key_event('toggle'));
        jwerty.key('⇞', IssuesListGroup.on_current_group_key_event('go_to_first_issue_if_opened'));
        jwerty.key('⇟', IssuesListGroup.on_current_group_key_event('go_to_last_issue_if_opened'));
    });

    IssuesListGroup.prototype.on_click = (function IssuesListGroup__on_click (e) {
        this.list.set_current();
        this.set_current(true);
        this.toggle(true);
        return false; // stop event propagation
    }); // IssuesListGroup__on_click

    IssuesListGroup.prototype.go_to_previous_item = (function IssuesListGroup__go_to_previous_item () {
        if (this.collapsed || this.no_visible_issues) { return; }
        // if we have no current issue, abort
        if (!this.current_issue) { return; }
        // try to select the previous issue
        var previous_issue = this.get_previous_issue();
        if (previous_issue) {
            previous_issue.set_current();
        } else {
            // no previous issue, select the current group itself
            this.set_active();
        }
        return false; // stop event propagation
    }); // IssuesListGroup__go_to_previous_item

    IssuesListGroup.prototype.go_to_next_item = (function IssuesListGroup__go_to_next_item () {
        if (this.collapsed || this.no_visible_issues) { return; }
        // if we have no current issue, select the first issue if we have one
        if (!this.current_issue) {
            if (!this.filtered_issues.length) { return; }
            this.filtered_issues[0].set_current();
            return false; // stop event propagation
        }
        // try to select the next issue
        var next_issue = this.get_next_issue();
        if (!next_issue) { return; }
        next_issue.set_current();
        return false; // stop event propagation
    }); // IssuesListGroup__go_to_next_item

    IssuesListGroup.prototype.go_to_first_issue = (function IssuesListGroup__go_to_first_issue (propagate) {
        if (this.collapsed || this.no_visible_issues) { return; }
        this.filtered_issues[0].set_current(propagate);
        return false; // stop event propagation
    }); // IssuesListGroup__go_to_first_issue

    IssuesListGroup.prototype.go_to_first_issue_if_opened = (function IssuesListGroup__go_to_first_issue_if_opened (propagate) {
        if (!this.current_issue) { return; }
        return this.go_to_first_issue(propagate);
    }); // IssuesListGroup__go_to_first_issue_if_opened

    IssuesListGroup.prototype.go_to_last_issue = (function IssuesListGroup__go_to_last_issue (propagate) {
        if (this.collapsed || this.no_visible_issues) { return; }
        this.filtered_issues[this.filtered_issues.length-1].set_current(propagate);
        return false; // stop event propagation
    }); // IssuesListGroup__go_to_last_issue

    IssuesListGroup.prototype.go_to_last_issue_if_opened = (function IssuesListGroup__go_to_last_issue_if_opened (propagate) {
        if (!this.current_issue) { return; }
        return this.go_to_last_issue(propagate);
    }); // IssuesListGroup__go_to_last_issue_if_opened

    IssuesListGroup.prototype.get_previous_issue = (function IssuesListGroup__get_previous_issue () {
        if (!this.current_issue) { return false; }
        var pos = this.filtered_issues.indexOf(this.current_issue);
        if (pos < 1) { return null; }
        return this.filtered_issues[pos - 1];
    }); // IssuesListGroup__get_previous_issue

    IssuesListGroup.prototype.get_next_issue = (function IssuesListGroup__get_next_issue () {
        if (!this.current_issue) {
            if (!this.filtered_issues.length) { return null; }
            return this.filtered_issues[0];
        }
        var pos = this.filtered_issues.indexOf(this.current_issue);
        if (pos == this.filtered_issues.length - 1) { return null; }
        return this.filtered_issues[pos + 1];
    }); // IssuesListGroup__get_next_issue

    IssuesListGroup.prototype.on_show = (function IssuesListGroup__on_show () {
        this.collapsed = false;
    }); // IssuesListGroup__on_show

    IssuesListGroup.prototype.on_hide = (function IssuesListGroup__on_hide () {
        this.collapsed = true;
    }); // IssuesListGroup__on_hide

    IssuesListGroup.prototype.get_issue_by_ident = (function IssuesListGroup__get_issue_by_ident(issue_ident) {
        var issue = null;
        for (var i = 0; i < this.issues.length; i++) {
            if (this.issues[i].number == issue_ident.number
             && this.issues[i].repository == issue_ident.repository) {
                issue = this.issues[i];
                break;
            }
        }
        return issue;
    }); // IssuesListGroup__get_issue_by_ident

    IssuesListGroup.prototype.update_filtered_issues = (function IssuesListGroup__update_filtered_issues () {
        this.filtered_issues = [];
        for (var i = 0; i < this.issues.length; i++) {
            var issue = this.issues[i];
            if (!issue.$node.hasClass('hidden')) {
                this.filtered_issues.push(issue);
            }
        }
        this.no_visible_issues = this.filtered_issues.length === 0;
        var filtered_length = this.filtered_issues.length,
            total_length = this.issues.length;
        this.$count_node.text(filtered_length == total_length ? total_length : filtered_length + '/' + total_length);
    }); // update_filtered_issues


    var IssuesList = (function IssuesList__constructor (node) {
        this.node = node;
        this.node.IssuesList = this;
        this.$node = $(node);
        this.$search_input = this.$node.find('.quicksearch');
        if (!this.$search_input.length && this.$node.data('quicksearch')) {
            this.$search_input = $(this.$node.data('quicksearch'));
        }

        var list = this;
        this.groups = $.map(this.$node.find(IssuesListGroup.selector),
                        function(node) { return new IssuesListGroup(node, list); });
        this.current_group = null;
    }); // IssuesList__constructor

    IssuesList.selector = '.issues-list';
    IssuesList.all = [];
    IssuesList.current = null;
    IssuesList.prev_current = null;

    IssuesList.prototype.unset_current = (function IssuesList__unset_current () {
        IssuesList.prev_current = this;
        IssuesList.current = null;
    }); // IssuesList__unset_current

    IssuesList.prototype.set_current = (function IssuesList__set_current () {
        if (IssuesList.current) {
            IssuesList.current.unset_current();
        }
        IssuesList.current = this;
    }); // IssuesList__set_current

    IssuesList.init_all = (function IssuesList_init_all () {
        IssuesList.all = $.map($(IssuesList.selector),
                            function(node) { return new IssuesList(node); });
        if (!IssuesList.all.length) { return; }
        IssuesList.all[0].set_current();
        IssuesListIssue.init_events();
        IssuesListGroup.init_events();
        IssuesList.init_events();
    }); // IssuesList_init_all

    IssuesList.on_current_list_key_event = (function IssuesList_key_decorate (list_method) {
        var decorator = function(e) {
            if (!IssuesList.current) { return; }
            return IssuesList.current[list_method]();
        };
        return Ev.key_decorate(decorator);
    });

    IssuesList.init_events = (function IssuesList_init_event () {
        jwerty.key('p/k/↑', IssuesList.on_current_list_key_event('go_to_previous_item'));
        jwerty.key('n/j/↓', IssuesList.on_current_list_key_event('go_to_next_item'));
        jwerty.key('⇞', IssuesList.on_current_list_key_event('go_to_first_group'));
        jwerty.key('⇟', IssuesList.on_current_list_key_event('go_to_last_group'));
        jwerty.key('f', IssuesList.on_current_list_key_event('focus_search_input'));
        jwerty.key('ctrl+u', IssuesList.on_current_list_key_event('clear_search_input'));
        jwerty.key('d', IssuesList.on_current_list_key_event('toggle_details'));
        for (var i = 0; i < IssuesList.all.length; i++) {
            var issues_list = IssuesList.all[i];
            if (issues_list.$search_input.length) {
                issues_list.$search_input.on('quicksearch.after', $.proxy(issues_list.on_filter_done, issues_list));
                issues_list.$search_input.on('keydown', jwerty.event('↑', issues_list.go_to_previous_item, issues_list));
                issues_list.$search_input.on('keydown', jwerty.event('↓', issues_list.go_to_next_item, issues_list));
                issues_list.$search_input.on('keydown', jwerty.event('return', issues_list.go_to_first_issue, issues_list))
            }
        }

        // keyboard events
        $document.on('click', '#toggle-issues-details', Ev.stop_event_decorate_dropdown(IssuesList.on_current_list_key_event('toggle_details')));
        $document.on('click', '#close-all-groups', Ev.stop_event_decorate_dropdown(IssuesList.on_current_list_key_event('close_all_groups')));
        $document.on('click', '#open-all-groups', Ev.stop_event_decorate_dropdown(IssuesList.on_current_list_key_event('open_all_groups')));
    }); // IssuesList_init_event

    IssuesList.prototype.on_filter_done = (function IssuesList__on_filter_done () {
        var continue_issue_search = this.$search_input.val() !== '';
        for (var i = 0; i < this.groups.length; i++) {
            var group = this.groups[i];
            group.update_filtered_issues();
            if (continue_issue_search !== false) {
                continue_issue_search = group.go_to_first_issue(true);
                if (continue_issue_search === false) {
                    this.$search_input.focus();
                }
            }
        }
        if (continue_issue_search !== false) {
            this.go_to_first_group();
            this.$search_input.focus();
        }

    }); // on_filter_done

    IssuesList.prototype.focus_search_input = (function IssuesList__focus_search_input () {
        if (!this.$search_input.length) { return; }
        this.$search_input.focus();
        return false;
    }); // IssuesList__focus_search_input

    IssuesList.prototype.clear_search_input = (function IssuesList__clear_search_input () {
        if (!this.$search_input.length) { return; }
        this.$search_input.val('');
        this.$search_input.trigger('quicksearch.refresh');
        return false;
    }); // IssuesList__clear_search_input

    IssuesList.prototype.go_to_previous_item = (function IssuesList__go_to_previous_item () {
        // if we have no current group, abort
        if (!this.current_group) { return; }
        // try to select the previous issue on the current group
        if (this.current_group.go_to_previous_item() === false) {
            return false; // stop event propagation
        }
        // no previous issue on the current group, try to select the previous group
        var previous_group = this.get_previous_group();
        if (!previous_group) {
            if (this.$search_input.length) {
                this.current_group.unset_current();
                this.$search_input.focus();
            }
            return false; // stop event propagation
        }
        if (previous_group.collapsed || previous_group.no_visible_issues) {
            previous_group.set_current(true);
        } else {
            previous_group.set_current();
            previous_group.go_to_last_issue();
        }
        return false; // stop event propagation
    }); // IssuesList__go_to_previous_item

    IssuesList.prototype.go_to_next_item = (function IssuesList__go_to_next_item () {
        // if we have no current group, select the first group if we have one
        if (!this.current_group) {
            if (!this.groups.length) { return; }
            this.groups[0].set_current(true);
            return false; // stop event propagation
        }
        // try to select the next issue on the current group
        if (this.current_group.go_to_next_item() === false) {
            return false; // stop event propagation
        }
        // no next issue on the current group, try to select the next group
        var next_group = this.get_next_group();
        if (!next_group) { return; }
        this.current_group.unset_current();
        next_group.set_current(true);
        return false; // stop event propagation
    }); // IssuesList__go_to_next_item

    IssuesList.prototype.go_to_first_issue = (function IssuesList__go_to_first_issue () {
        // select the first non empty group
        for (var i = 0; i < this.groups.length; i++) {
            var group = this.groups[i];
            if (!group.no_visible_issues) {
                group.set_current(true);
                break;
            }
        }
        if (!this.current_group) { return; }
        this.current_group.open();
        this.current_group.go_to_first_issue();
    }); // IssuesList__go_to_first_issue

    IssuesList.prototype.get_previous_group = (function IssuesList__get_previous_group () {
        if (!this.current_group) { return null; }
        var pos = this.groups.indexOf(this.current_group);
        if (pos < 1) { return null; }
        return this.groups[pos - 1];
    }); // IssuesList__get_previous_group

    IssuesList.prototype.get_next_group = (function IssuesList__get_next_group () {
        if (!this.current_group) {
            if (!this.groups.length) { return null; }
            return this.groups[0];
        }
        var pos = this.groups.indexOf(this.current_group);
        if (pos == this.groups.length - 1) { return null; }
        return this.groups[pos + 1];
    }); // IssuesList__get_next_group

    IssuesList.prototype.go_to_first_group = (function IssuesList__go_to_first_group () {
        if (!this.groups.length) { return; }
        this.groups[0].set_current(true);
        return false; // stop event propagation
    }); // IssuesList__go_to_first_group

    IssuesList.prototype.go_to_last_group = (function IssuesList__go_to_last_group () {
        if (!this.groups.length) { return; }
        this.groups[this.groups.length - 1].set_current(true);
        return false; // stop event propagation
    }); // IssuesList__go_to_last_group

    IssuesList.toggle_details = (function IssuesList_toggle_details () {
        for (var i = 0; i < IssuesList.all.length; i++) {
            var list = IssuesList.all[i];
            list.toggle_details();
        }
        return false; // stop event propagation
    }); // IssuesList_toggle_details

    IssuesList.prototype.toggle_details = (function IssuesList__toggle_details () {
        this.$node.toggleClass('without-details');
        for (var i = 0; i < this.groups.length; i++) {
            var group = this.groups[i];
            if (!group.collapsed) {
                group.$issues_node.height('auto');
            }
        }
        return false; // stop event propagation
    }); // IssuesList__toggle_details

    IssuesList.close_all_groups = (function IssuesList_close_all_groups () {
        for (var i = 0; i < IssuesList.all.length; i++) {
            var list = IssuesList.all[i];
            list.close_all_groups();
        }
        return false; // stop event propagation
    }); // IssuesList_close_all_groups

    IssuesList.prototype.close_all_groups = (function IssuesList__close_all_groups () {
        for (var i = 0; i < this.groups.length; i++) {
            var group = this.groups[i];
            group.close();
        }
        return false; // stop event propagation
    }); // IssuesList__close_all_groups

    IssuesList.open_all_groups = (function IssuesList_open_all_groups () {
        for (var i = 0; i < IssuesList.all.length; i++) {
            var list = IssuesList.all[i];
            list.open_all_groups();
        }
        return false; // stop event propagation
    }); // IssuesList_open_all_groups

    IssuesList.prototype.open_all_groups = (function IssuesList__open_all_groups () {
        for (var i = 0; i < this.groups.length; i++) {
            var group = this.groups[i];
            group.open();
        }
        return false; // stop event propagation
    }); // IssuesList__open_all_groups

    IssuesList.get_issue_by_ident = (function IssuesList_get_issue_by_ident(issue_ident) {
        var issue = null;
        for (var i = 0; i < IssuesList.all.length; i++) {
            issue = IssuesList.all[i].get_issue_by_ident(issue_ident);
            if (issue) { break; }
        }
        return issue;
    }); // IssuesList_get_issue_by_ident

    IssuesList.prototype.get_issue_by_ident = (function IssuesList__get_issue_by_ident(issue_ident) {
        var issue = null;
        for (var i = 0; i < this.groups.length; i++) {
            issue = this.groups[i].get_issue_by_ident(issue_ident);
            if (issue) { break; }
        }
        return issue;
    }); // IssuesList__get_issue_by_ident

    IssuesList.init_all();

    var IssuesFilters = {
        on_filter_shown: (function IssuesFilters__on_filter_shown (ev) {
            var $collapse = $(ev.target);
            if ($collapse.hasClass('deferred')) {
                $collapse.trigger('reload');
                ev.stopPropagation();
            } else {
                IssuesFilters.focus_quicksearch_filter($collapse);
            }
        }), // on_filter_shown
        on_deferrable_loaded: (function IssuesFilters__on_deferrable_loaded (ev) {
            IssuesFilters.focus_quicksearch_filter($(ev.target));
        }), // on_deferrable_loaded
        focus_quicksearch_filter: (function IssuesFilters__focus_quicksearch_filter ($filter_node) {
            $filter_node.find('input.quicksearch').focus();
        }), // focus_quicksearch_filter
        init: function() {
            var $filters = $('#issues-filters');
            if ($filters.length) {
                $filters.find('.collapse').on('shown.collapse', IssuesFilters.on_filter_shown);
                $filters.on('reloaded', IssuesFilters.on_deferrable_loaded);
            }
        }
    };
    IssuesFilters.init();

    var IssueByNumber = {
        $window: $('#go-to-issue-window'),
        $form: $('#go-to-issue-window form'),
        $input: $('#go-to-issue-window form input'),
        open: (function IssueByNumber_open () {
            IssueByNumber.$window.modal('show');
            return false; // stop event propagation
        }), // IssueByNumber_open
        on_show: (function IssueByNumber_on_show (e) {
            IssueByNumber.$input.val('');
        }), // IssueByNumber_on_show
        on_shown: (function IssueByNumber_on_shown (e) {
            setTimeout(function() {
                IssueByNumber.$input.focus();
                IssueByNumber.$input.prop('placeholder', "Type an issue number");
            }, 250);
        }), //IssueByNumber_on_shown
        on_submit: (function IssueByNumber_on_submit (e) {
            var number = IssueByNumber.$input.val(),
                fail = false;
            if (!number) {
                fail = true;
            } else if (number[0] == '#') {
                number = number.slice(1);
            }
            IssueByNumber.$input.val('');
            if (!fail && !isNaN(number)) {
                IssueByNumber.$window.modal('hide');
                IssueByNumber.$input.prop('placeholder', "Type an issue number");
                IssueByNumber.open_issue({
                    number: number,
                    repository: main_repository
                });
            } else {
                IssueByNumber.$input.prop('placeholder', "Type a correct issue number");
            IssueByNumber.$input.focus();
            }
            return false; // stop event propagation
        }), // IssueByNumber_on_submit
        open_issue: (function IssueByNumber_open_issue (issue_ident) {
            IssuesListIssue.open_issue(issue_ident);
        }), // IssueByNumber_open_issue
        init_events: (function IssueByNumber_init_events () {
            if (!IssueByNumber.$window.length) { return; }
            $document.on('keypress', Ev.key_decorate(Ev.charcode(35, IssueByNumber.open)));  // 35 = #
            jwerty.key('i', Ev.key_decorate(IssueByNumber.open));
            IssueByNumber.$window.on('show.modal', IssueByNumber.on_show);
            IssueByNumber.$window.on('shown.modal', IssueByNumber.on_shown);
            IssueByNumber.$form.on('submit', Ev.stop_event_decorate(IssueByNumber.on_submit));
        }) // IssueByNumber_init_events
    }; // IssueByNumber

    IssueByNumber.init_events();

    var toggle_full_screen_for_current_modal = (function toggle_full_screen_for_current_modal(ev) {
        var $modal = $('.modal.in');
        if ($modal.length) {
            if ($modal.length > 1) {
                // get one with higher z-index
                $modal = $($modal.sort(function(a, b) { return $(b).css('zIndex') - $(a).css('zIndex'); })[0]);
            }
            $modal.toggleClass('full-screen');
            if (IssueDetail.is_modal_an_IssueDetail($modal)) {
                // continue to IssueDetail.toggle_full_screen if the modal is a IssueDetail
                return true;
            }
            return false; // stop event propagation
        }
    }); // toggle_full_screen_for_current_modal
    jwerty.key('s', Ev.key_decorate(toggle_full_screen_for_current_modal));

    var on_help = (function on_help(e) {
        $('#show-shortcuts').click();
        return false; // stop event propagation
    }); // on_help

    if ($('#show-shortcuts').length) {
        $document.on('keypress', Ev.key_decorate(Ev.charcode(63, on_help)));  // 63 = ?
    }

    var IssueDetail = {
        $main_container: $('#main-issue-container'),
        $modal: $('#modal-issue-view'),
        $modal_body: null,  // set in __init__
        $modal_container: null,  // set in __init__

        get_url_for_ident: (function IssueDetail__get_url_for_ident (issue_ident) {
            var number = issue_ident.number.toString(),
                result = '/' + issue_ident.repository + '/issues/';
            if (number.indexOf('pk-') == 0) {
                result += 'created/' + number.substr(3);
            } else {
                result += number;
            }
            return result + '/';
        }), // get_url_for_ident

        on_issue_loaded: (function IssueDetail__on_issue_loaded ($node, focus_modal) {
            var is_modal = IssueDetail.is_modal($node);
            if (is_modal && focus_modal) {
                // focusing $node doesn't FUCKING work
                setTimeout(function() {
                    $node.find('header h3 a').focus();
                }, 250);
            }
            // display the repository name if needed
            $node.toggleClass('with-repository', $node.data('repository') != main_repository);
            // set waypoints
            IssueDetail.set_issue_waypoints($node, is_modal);
            IssueDetail.scroll_tabs($node, true);
        }), // on_issue_loaded

        get_scroll_context: (function IssueDetail__get_scroll_context ($node, is_modal) {
            if (typeof is_modal === 'undefined') {
                is_modal = IssueDetail.is_modal($node);
            }
            return is_modal ? $node.parent() : $node;
        }), // get_scroll_context

        get_repository_name_height: (function IssueDetail__get_repository_name_height ($node) {
            return $node.hasClass('with-repository') ? 30 : 0;
        }), // get_repository_name_height

        set_issue_waypoints: (function IssueDetail__set_issue_waypoints ($node, is_modal) {
            var issue_ident = IssueDetail.get_issue_ident($node);
            $node.removeClass('header-stuck');
            setTimeout(function() {
                if (!IssueDetail.is_issue_ident_for_node($node, issue_ident)) { return; }
                var $context = IssueDetail.get_scroll_context($node, is_modal);
                $node.find(' > article > .area-top header').waypoint('sticky', {
                    context: $context,
                    wrapper: '<div class="sticky-wrapper area-top-header-sticky-wrapper" />',
                    stuckClass: 'area-top stuck',
                    handler: function(direction) {
                        $node.toggleClass('header-stuck', direction == 'down');
                    }
                });
                var $tabs = $node.find('.issue-tabs');
                if ($tabs.length) {
                    $tabs.waypoint('sticky', {
                        context: $context,
                        wrapper: '<div class="sticky-wrapper issue-tabs-sticky-wrapper" />',
                        stuckClass: 'area-top stuck',
                        offset: 47 + IssueDetail.get_repository_name_height($node), // stuck header height
                        handler: function(direction) {
                            setTimeout(function() { IssueDetail.scroll_tabs($node); }, 500);
                        }
                    })
                }
            }, 500);
        }), // set_issue_waypoints

        set_tab_files_waypoints: (function IssueDetail__set_tab_files_waypoints ($node, $tab_pane, $context) {
            var $files_list_container = $tab_pane.find('.code-files-list-container');
            if ($files_list_container.length) {
                if (!$context) {
                    $context = IssueDetail.get_scroll_context($node);
                }
                $files_list_container.waypoint('sticky', {
                    context: $context,
                    wrapper: '<div class="sticky-wrapper files-list-sticky-wrapper" />',
                    offset: 47 + 37 + IssueDetail.get_repository_name_height($node)  // 47 for stuck header height + 37 for stuck tabs height
                });
            }
        }), // set_tab_files_waypoints

        set_tab_review_waypoints: (function IssueDetail__set_tab_review_issue_waypoints ($node, $tab_pane, $context) {
            var $review_header = $tab_pane.find('.review-header');
            if ($review_header.length) {
                if (!$context) {
                    $context = IssueDetail.get_scroll_context($node);
                }
                $review_header.waypoint('sticky', {
                    context: $context,
                    wrapper: '<div class="sticky-wrapper review-header-sticky-wrapper" />',
                    offset: 47 + 37 + IssueDetail.get_repository_name_height($node)  // 47 for stuck header height + 37 for stuck tabs height
                });
            }
        }), // set_tab_review_issue_waypoints

        unset_issue_waypoints: (function IssueDetail__unset_issue_waypoints ($node) {
            $node.find(' > article > .area-top header').waypoint('unsticky');
            $node.find('.issue-tabs').waypoint('unsticky');
            $node.find('.code-files-list-container').each(function() {
                $(this).waypoint('unsticky');
            });
            $node.find('.review-header').each(function() {
                $(this).waypoint('unsticky');
            });
        }), // unset_issue_waypoints

        unset_tab_files_waypoints: (function IssueDetail__unset_tab_files_waypoints ($tab_pane) {
            $tab_pane.find('.code-files-list-container').waypoint('unsticky');
        }), // unset_tab_files_waypoints

        is_modal: (function IssueDetail__is_modal ($node) {
            return !!$node.data('$modal');
        }), // is_modal

        enhance_modal: (function IssueDetail__enhance_modal ($node) {
            $node.find('.issue-nav ul').append('<li class="divider"></li><li><a href="#" data-dismiss="modal"><i class="fa fa-times fa-fw"> </i> Close window</a></li>');
        }), // enhance_modal

        get_container: (function IssueDetail__get_container (force_popup) {
            var panel = {
                $window: null,
                $node: IssueDetail.$main_container,
                $scroll_node: IssueDetail.$main_container,
                after: null
            }, popup = {
                $window: IssueDetail.$modal,
                $node: IssueDetail.$modal_container,
                $scroll_node: IssueDetail.$modal_body,
                after: IssueDetail.enhance_modal
            };
            return (force_popup || !IssueDetail.$main_container.length) ? popup : panel;
        }), // get_container

        is_issue_ident_for_node: (function IssueDetail__is_issue_ident_for_node($node, issue_ident) {
            var existing_ident = IssueDetail.get_issue_ident($node);
            return (existing_ident.number == issue_ident.number && existing_ident.repository == issue_ident.repository);
        }), // is_issue_ident_for_node

        get_issue_ident: (function IssueDetail__get_issue_ident($node) {
            return {
                number: $node.data('number'),
                repository: $node.data('repository')
            };
        }), // get_issue_ident

        set_issue_ident: (function IssueDetail__set_issue_ident($node, issue_ident) {
            $node.data('number', issue_ident.number);
            $node.data('repository', issue_ident.repository);
        }), // set_issue_ident

        get_container_waiting_for_issue: (function IssueDetail__get_container_waiting_for_issue (issue_ident, force_popup, force_load) {
            var container = IssueDetail.get_container(force_popup),
                is_popup = (force_popup || container.$window);
            if (!force_load && !is_popup && IssueDetail.is_issue_ident_for_node(container.$node, issue_ident)) {
                return false;
            }
            IssueDetail.set_issue_ident(container.$node, issue_ident);
            if (container.$window && !container.$window.hasClass('in')) {
                // open the popup with its loading spinner
                container.$window.modal("show");
            }
            return container;
        }), // get_container_waiting_for_issue

        fill_container: (function IssueDetail__fill_container (container, html) {
            if (typeof $().select2 != 'undefined') {
                container.$node.find('select.select2-offscreen').select2('destroy');
            }
            container.$node.html(html);
            container.$scroll_node.scrollTop(1);  // to move the scrollbar (WTF !)
            container.$scroll_node.scrollTop(0);
        }), // fill_container

        display_issue: (function IssueDetail__display_issue (html, issue_ident, force_popup) {
            var container = IssueDetail.get_container(force_popup);
            if (!this.is_issue_ident_for_node(container.$node, issue_ident)) { return; }
            IssueDetail.fill_container(container, html);
            IssueDetail.on_issue_loaded(container.$node, true);
            if (container.after) {
                container.after(container.$node);
            }
            MarkdownManager.update_links();
        }), // display_issue

        clear_container: (function IssueDetail__clear_container (error, force_popup) {
            var container = IssueDetail.get_container(force_popup);
            IssueDetail.unset_issue_waypoints(container.$node);
            IssueDetail.set_issue_ident(container.$node, {number: 0, repository: ''});
            IssueDetail.fill_container(container, '<p class="empty-area">' + (error ? error + ' :(' : '...') + '</p>');
        }), // clear_container

        set_container_loading: (function IssueDetail__set_container_loading (container) {
            IssueDetail.unset_issue_waypoints(container.$node);
            IssueDetail.fill_container(container, '<p class="empty-area"><i class="fa fa-spinner fa-spin"> </i></p>');
        }), // set_container_loading

        select_tab: (function IssueDetail__select_tab (panel, type) {
            var $tab_link = panel.$node.find('.' + type + '-tab > a');
            if ($tab_link.length) { $tab_link.tab('show'); }
            return false;
        }), // select_tab
        select_discussion_tab: function(panel) { return IssueDetail.select_tab(panel, 'pr-discussion'); },
        select_commits_tab: function(panel) { return IssueDetail.select_tab(panel, 'pr-commits'); },
        select_files_tab: function(panel) { return IssueDetail.select_tab(panel, 'pr-files'); },
        select_review_tab: function(panel) { return IssueDetail.select_tab(panel, 'pr-review'); },

        on_files_list_loaded: (function IssueDetail__on_files_list_loaded ($node, $tab_pane) {
            if ($tab_pane.data('files-list-loaded')) { return; }
            $tab_pane.data('files-list-loaded', true);
            IssueDetail.set_tab_files_waypoints($node, $tab_pane);
            $tab_pane.find('.code-files-list a.path').first().click();
        }), // on_files_list_loaded

        on_files_list_click: (function IssueDetail__on_files_list_click (ev) {
            var $link = $(this),
                $target = $($link.attr('href')),
                $node = $link.closest('.issue-container'),
                $tab_pane = $link.closest('.tab-pane');
            IssueDetail.scroll_in_files_list($node, $tab_pane, $target, -20); // -20 = margin
            IssueDetail.set_active_file($tab_pane, $link.closest('tr').data('pos'), true);
            if (!ev.no_file_focus) {
                $target.find('.box-header a.path').focus();
            }
            return false;
        }), // on_files_list_click

        on_review_loaded: (function IssueDetail__on_review_loaded ($node, $tab_pane) {
            if ($tab_pane.data('review-loaded')) { return; }
            $tab_pane.data('review-loaded', true);
            IssueDetail.set_tab_review_waypoints($node, $tab_pane);
        }), // on_review_loaded

        get_sticky_wrappers_classes_for_tab: (function IssueDetail__get_sticky_wrappers_for_tab ($node, $tab_pane) {
            var wrapper_classes = {
                node: ['area-top-header-sticky-wrapper', 'issue-tabs-sticky-wrapper'],
                tab: ['files-list-sticky-wrapper']
            };
            return wrapper_classes;
        }), // get_sticky_wrappers_for_tab

        compute_sticky_wrappers_height: (function IssueDetail__compute_sticky_wrappers_height ($node, $tab_pane, wrapper_classes) {
            var wrappers = [], i, j, height=0;
            for (i = 0; i < wrapper_classes.node.length; i++) {
                wrappers.push($node.find('.' + wrapper_classes.node[i]));
            };
            for (j = 0; j < wrapper_classes.tab.length; j++) {
                wrappers.push($tab_pane.find('.' + wrapper_classes.tab[j]));
            };
            height = $(wrappers)
                        .toArray()
                        .reduce(function(height, wrapper) {
                            var $wrapper = $(wrapper),
                                $stickable = $wrapper.children().first();
                            return height + ($stickable.hasClass('stuck') ? $stickable : $wrapper).outerHeight();
                        }, 0);
            return height;
        }), // compute_sticky_wrappers_height

        scroll_in_files_list: (function IssueDetail__scroll_in_files_list ($node, $tab_pane, $target, delta) {
            var is_modal = IssueDetail.is_modal($node),
                $context = IssueDetail.get_scroll_context($node, is_modal),
                is_list_on_top = !Math.round(parseFloat($tab_pane.find('.code-files-list-container').css('border-right-width'))),
                // is_full_screen = ($node.hasClass('big-issue')),
                sticky_wrappers = IssueDetail.get_sticky_wrappers_classes_for_tab($node, $tab_pane),
                stuck_height, position;

            if (!is_list_on_top && sticky_wrappers.tab.indexOf('files-list-sticky-wrapper') >= 0) {
                sticky_wrappers.tab.splice( sticky_wrappers.tab.indexOf('files-list-sticky-wrapper'));
            }

            stuck_height = IssueDetail.compute_sticky_wrappers_height($node, $tab_pane, sticky_wrappers);

            position = (is_modal ? $target.position().top : $target.offset().top)
                     + (is_modal ? 0 : $context.scrollTop())
                     - stuck_height
                     + (is_modal ? (is_list_on_top ? 65 : 445) : 10) // manual finding... :(
                     - 47 // topbar
                     + (delta || 0);

            $context.scrollTop(Math.round(0.5 + position));

            IssueDetail.highlith_on_scroll($target);
        }), // scroll_in_files_list

        highlith_on_scroll: (function IssueDetail__highlith_on_scroll($target, delay) {
            if (typeof delay == 'undefined') { delay = 700; }
            $target.addClass('scroll-highlight');
            setTimeout(function() { $target.removeClass('scroll-highlight'); }, delay);
        }), // highlith_on_scroll

        on_files_list_toggle: (function IssueDetail__on_files_list_toggle (ev) {
            var $files_list = $(this),
                $container = $files_list.closest('.code-files-list-container');
            if ($container.hasClass('stuck')) {
                $container.parent().height($container.outerHeight());
            }
            if ($files_list.hasClass('in')) {
               IssueDetail.set_active_file_visible($files_list.closest('.tab-pane'), $files_list);
            }
        }), // on_files_list_toggle

        toggle_files_list: (function IssueDetail__toggle_files_list () {
            var $node = $(this).closest('.issue-container'),
                $tab_pane = $node.find('.tab-pane.active'),
                $link = $tab_pane.find('.code-files-list-container .files-list-summary');
            if ($link.length) { $link.click(); }
        }), // toggle_files_list

        on_file_mouseenter: (function IssueDetail__on_file_mouseenter (ev) {
            var $file_node = $(this),
                $tab_pane = $file_node.closest('.tab-pane');
            IssueDetail.set_active_file($tab_pane, $file_node.data('pos'), false);
        }), // on_file_mouseenter

        go_to_previous_file: (function IssueDetail__go_to_previous_file () {
            var $node = $(this).closest('.issue-container'),
                $tab_pane = $node.find('.tab-pane.active'),
                $files_list = $tab_pane.find('.code-files-list'),
                $current_line = $files_list.find('tr.active'),
                $line = $current_line.prevAll('tr:not(.hidden)').first();
            if ($line.length) {
                $line.find('a').click();
            }
            return false;
        }), // go_to_previous_file

        go_to_next_file: (function IssueDetail__go_to_next_file () {
            var $node = $(this).closest('.issue-container'),
                $tab_pane = $node.find('.tab-pane.active'),
                $files_list = $tab_pane.find('.code-files-list'),
                $current_line = $files_list.find('tr.active'),
                $line = $current_line.nextAll('tr:not(.hidden)').first();
            if ($line.length) {
                $line.find('a').click();
            }
            return false;
        }), // go_to_next_file

        on_files_filter_done: (function IssueDetail__on_files_filter_done () {
            var $tab_pane = $(this).closest('.tab-pane');
            if (!$tab_pane.find('.files-tab.active').length) { return; }
            var $files_list = $tab_pane.find('.code-files-list'),
                $first_link = $files_list.find('tr:not(.hidden) a').first();
            if (($first_link).length) {
                $first_link.trigger({type: 'click', no_file_focus: true});
            }
        }), // on_files_filter_done

        set_active_file: (function IssueDetail__set_active_file ($tab_pane, pos, reset_active_comment) {
            var $files_list = $tab_pane.find('.code-files-list'),
                $line;
            if (!$files_list.length) { return; }
            if (pos == '999999') {
                $line = $files_list.find('tr:last-child');
            } else {
                $line = $files_list.find('tr:nth-child('+ pos +')');
            }
            $files_list.find('tr.active').removeClass('active');
            $line.addClass('active');
            IssueDetail.set_active_file_visible($tab_pane, $files_list, $line);
            $tab_pane.find('.go-to-previous-file').parent().toggleClass('disabled', $line.prevAll('tr:not(.hidden)').length === 0);
            $tab_pane.find('.go-to-next-file').parent().toggleClass('disabled', $line.nextAll('tr:not(.hidden)').length === 0);
            if (reset_active_comment) {
                $files_list.closest('.code-files-list-container').data('active-comment', null);
                $tab_pane.find('.go-to-previous-file-comment, .go-to-next-file-comment').parent().removeClass('disabled');
            }
        }), // set_active_file

        set_active_file_visible: (function IssueDetail__set_active_file_visible ($tab_pane, $files_list, $line) {
            var line_top, line_height, list_visible_height, list_scroll;
            if (typeof $files_list == 'undefined') {
                $files_list = $tab_pane.find('.code-files-list');
            }
            // files list not opened: do nothing
            if (!$files_list.hasClass('in')) {
                return;
            }
            if (typeof $line == 'undefined') {
                $line = $files_list.find('tr.active');
            }
            // no active line: do nothing
            if (!$line.length) {
                return;
            }
            line_top = $line.position().top;
            list_scroll = $files_list.scrollTop();
            // above the visible part of the list: set it visible at top
            if (line_top < 0) {
                $files_list.scrollTop(Math.round(0.5 + list_scroll + line_top));
                return;
            }
            line_height = $line.height();
            list_visible_height = $files_list.height();
            // in the visible part: do nothing
            if (line_top + line_height < list_visible_height) {
                return;
            }
            // below the visible part: set it visible at the bottom
            $files_list.scrollTop(Math.round(0.5 + list_scroll + line_top - list_visible_height + line_height));
        }), // set_active_file_visible

        visible_files_comments: (function IssueDetail__visible_files_comments ($tab_pane) {
            var $files_list = $tab_pane.find('.code-files-list');
            if ($files_list.length) {
                return $files_list.find('tr:not(.hidden) a')
                            .toArray()
                            .reduce(function(groups, file_link) {
                                return groups.concat($(
                                    $(file_link).attr('href')
                                ).find('.code-comments').toArray());
                            }, [])
                            .concat($tab_pane.find('.global-comments').toArray());
            } else {
                return [];
            }
        }), // visible_files_comments

        go_to_previous_file_comment: (function IssueDetail__go_to_previous_file_comment () {
            var $node = $(this).closest('.issue-container'),
                $tab_pane = $node.find('.tab-pane.active');
            IssueDetail.go_to_file_comment($node, $tab_pane, 'previous');
            return false;
        }), // go_to_previous_file_comment

        go_to_next_file_comment: (function IssueDetail__go_to_next_file_comment () {
            var $node = $(this).closest('.issue-container'),
                $tab_pane = $node.find('.tab-pane.active');
            IssueDetail.go_to_file_comment($node, $tab_pane, 'next');
            return false;
        }), // go_to_next_file_comment

        go_to_file_comment: (function IssueDetail__go_to_file_comment ($node, $tab_pane, direction) {
            var $files_list_container = $tab_pane.find('.code-files-list-container'),
                $files_list = $tab_pane.find('.code-files-list'),
                comments = IssueDetail.visible_files_comments($tab_pane),
                current, comment, $comment, $file_node, position, file_pos, index;

            if (!comments.length) { return; }

            current = $files_list_container.data('active-comment');

            if (current) {
                // we are on a comment, use it as a base
                index = comments.indexOf(current) + (direction === 'previous' ? -1 : +1);
            } else {
                if ($files_list.length) {
                    // we have a list of files, get index based on position
                    $file_node = $($files_list.find('tr.active a').attr('href'));
                    file_pos = $file_node.data('pos');
                    index = -1;
                    for (var i = 0; i < comments.length; i++) {
                        if ($(comments[i]).closest('.code-file').data('pos') >= file_pos) {
                            // we are at the first comment for/after the file:
                            //  - if we wanted the next, we got it
                            //  - if we wanted the previous, return it if we previously has one, else go 0
                            index = direction == 'next' ? i : (index >= 0 ? index : 0);
                            break;
                        } else if (direction == 'previous') {
                            // we are before the file, mark the one found as the last one
                            // and continue: the last one will be used when the loop end
                            // or if we pass the current file
                            index = i;
                        }
                    }
                } else {
                    // we have only one file, go to the first comment
                    index = 0;
                }
            }
            if (!((index || index === 0) && index >= 0 && index < comments.length)) {
                index = 0;
            }
            comment = comments[index];
            $comment = $(comment);
            $file_node = $comment.closest('.code-file');
            $files_list_container.data('active-comment', comment);
            IssueDetail.set_active_file($tab_pane, $file_node.data('pos'), false);
            IssueDetail.scroll_in_files_list($node, $tab_pane, $comment, -50);  // -20=margin, -30 = 2 previous diff lines
            $comment.focus();
            $tab_pane.find('.go-to-previous-file-comment').parent().toggleClass('disabled', index < 1);
            $tab_pane.find('.go-to-next-file-comment').parent().toggleClass('disabled', index >= comments.length - 1);
        }), // go_to_file_comment

        go_to_previous_review_comment: (function IssueDetail__go_to_previous_review_comment () {
            var $node = $(this).closest('.issue-container'),
                $tab_pane = $node.find('.tab-pane.active');
            IssueDetail.go_to_review_comment($node, $tab_pane, 'previous');
            return false;
        }), // go_to_previous_review_comment

        go_to_next_review_comment: (function IssueDetail__go_to_next_review_comment () {
            var $node = $(this).closest('.issue-container'),
                $tab_pane = $node.find('.tab-pane.active');
            IssueDetail.go_to_review_comment($node, $tab_pane, 'next');
            return false;
        }), // go_to_next_review_comment

        go_to_review_comment: (function IssueDetail__go_to_review_comment ($node, $tab_pane, direction) {
            var current_index = $tab_pane.data('current-index'),
                $all_blocks = $tab_pane.find('.pr-entry-point'),
                step = direction == 'next' ? 1 : -1,
                index = (typeof current_index == 'undefined' ? -1 : current_index) + step,
                $final_node, $container, do_scroll;

            if (index < 0 || index >= $all_blocks.length) { return; }

            for (var i = index; 0 <= i < $all_blocks.length; i+=step) {
                if (!$($all_blocks[i]).hasClass('hidden')) {
                    break;
                }
                index ++;
            };

            if (index < 0 || index >= $all_blocks.length) { return; }

            $final_node = $($all_blocks[index]);
            do_scroll = function() {
                IssueDetail.scroll_in_review($node, $tab_pane, $final_node, -20);
            };
            $container = $final_node.children('.collapse');
            if (!$container.hasClass('in')) {
                $container.one('shown.collapse', do_scroll);
                $container.collapse('show');
            } else {
               do_scroll();
            }
            IssueDetail.mark_current_review_comment($tab_pane, $final_node);

        }), // go_to_review_comment

        mark_current_review_comment: (function IssueDetail__mark_current_review_comment ($tab_pane, $target) {
            var $all_blocks = $tab_pane.find('.pr-entry-point'),
                $block = $target.closest('.pr-entry-point'),
                index = $all_blocks.toArray().indexOf($block[0]);
            $target.focus();
            $tab_pane.data('current-index', index);
            $tab_pane.find('.go-to-previous-review-comment').parent().toggleClass('disabled', index < 1);
            $tab_pane.find('.go-to-next-review-comment').parent().toggleClass('disabled', index >= $all_blocks.length - 1);
        }), // mark_current_review_comment

        go_to_global_comments: (function IssueDetail__go_to_global_comments () {
            var $tab_pane = $(this).closest('.tab-pane'),
                $node = $(this).closest('.issue-container'),
                $global_comments = $tab_pane.find('.global-comments');
            IssueDetail.scroll_in_files_list($node, $tab_pane, $global_comments, -50);  // -20=margin, -30 = 2 previous diff lines
            return false;
        }), // go_to_global_comments

        scroll_in_review: (function IssueDetail__scroll_in_review ($node, $tab_pane, $target, delta) {
            var is_modal = IssueDetail.is_modal($node),
                $context = IssueDetail.get_scroll_context($node, is_modal),
                sticky_wrappers = IssueDetail.get_sticky_wrappers_classes_for_tab($node, $tab_pane),
                stuck_height = IssueDetail.compute_sticky_wrappers_height($node, $tab_pane, sticky_wrappers),
                position = (is_modal ? $target.position().top : $target.offset().top)
                         + (is_modal ? 0 : $context.scrollTop())
                         - stuck_height
                         + (is_modal ? 60 : 5) // manual finding... :(
                         - 55 // review-header
                         - 47 // topbar;
                         + (delta || 0);

                $context.scrollTop(Math.round(0.5 + position));

            IssueDetail.highlith_on_scroll($target);
        }), // scroll_in_review

        before_load_tab: (function IssueDetail__before_load_tab (ev) {
            if (!ev.relatedTarget) { return; }
            var $previous_tab = $(ev.relatedTarget),
                $previous_target = $($previous_tab.attr('href')),
                $node = $previous_tab.closest('.issue-container'),
                is_modal = IssueDetail.is_modal($node),
                $context = IssueDetail.get_scroll_context($node, is_modal);
            $previous_target.data('scroll-position', $context.scrollTop());
        }), // before_load_tab

        scroll_tabs: (function IssueDetail__scroll_tabs($node, force_arrows, $force_tab) {
            var $tabs_scroller = $node.find('.issue-tabs'),
                $tabs_holder = $tabs_scroller.children('ul'),
                $all_tabs = $tabs_holder.children('li:visible'),
                $tab,
                current_offset, final_offset,
                tabs_holder_width, full_width,
                tab_position, tab_left, tab_right,
                $last_tab, last_tab_right,
                show_left_arrow = false, count_left = 0,
                show_right_arrow = false, count_right = 0;

            // manage tabs bar visibility
            if ($all_tabs.length == 1) {
                // tabs bar is visible but only one tab, hide the bar
                $tabs_scroller.hide()
                return;
            } else if ($all_tabs.length == 0) {
                // tabs bar seems hidden, count number of tabs that are "visible"
                // (:visible doesn't work if a parent is hidden)
                if ($tabs_holder.children('li:not(.template)').length < 2) {
                    // ok max one tab visible, keep the tabs bar hidden
                    return;
                }
                // more that one tab visible, display the tab bar
                $tabs_scroller.show();
                $all_tabs = $tabs_holder.children('li:visible');
                force_arrows = true;
            }

            // do lots of computation...
            $tab = (typeof $force_tab == 'undefined')
                    ? $tabs_holder.children('li.active')
                    : $force_tab;
            current_offset = $tabs_scroller.data('scroll-offset') || 0;
            final_offset = current_offset;
            tabs_holder_width = $tabs_scroller.innerWidth() - 50;  // padding for arrows !
            full_width = tabs_holder_width + current_offset;
            tab_position = $tab.position();
            tab_left = tab_position.left - 3;
            tab_right = tab_position.left + $tab.outerWidth() + 3;
            $last_tab = $all_tabs.last();
            last_tab_right = $last_tab.position().left + $last_tab.outerWidth() + 3;


            // fond wanted offset for tab we want to show
            if (tab_left < current_offset) {
                final_offset = tab_left;
            } else if (tab_right > full_width) {
                final_offset = current_offset + tab_right - full_width;
            } else if (last_tab_right < full_width) {
                final_offset = current_offset - (full_width - last_tab_right);
                if (final_offset < 0) { final_offset = 0; }
            }

            // apply offset the the tabs bar
            if (final_offset != current_offset) {
                if (transform_attribute) {
                    $tabs_holder.css('transform', 'translateX(' + (-final_offset) + 'px)');
                } else {
                    $tabs_holder.css('left', (-final_offset) + 'px');
                }
                $tabs_scroller.data('scroll-offset', final_offset);
            }

            // manage counters and arrows
            if (force_arrows || final_offset != current_offset) {

                // update counter of hidden tabs on the left
                if (final_offset > 0) {
                    show_left_arrow = true;
                    for (var i = 0; i < $all_tabs.length; i++) {
                        $tab = $($all_tabs[i]);
                        tab_left = $tab.position().left - 3;
                        if ( tab_left >= final_offset) {
                            break;
                        }
                        count_left += 1;
                    };
                    $tabs_scroller.data('next-left-tab', count_left ? $all_tabs[i-1]: null)
                                  .find('.scroll-left .badge').text(count_left);
                }

                // update counter of hidden tabs on the right
                full_width = tabs_holder_width + final_offset
                if (last_tab_right > full_width) {
                    show_right_arrow = true;
                    for (var j = 0; j < $all_tabs.length; j++) {
                        $tab = $($all_tabs[j]);
                        tab_right = $tab.position().left  + $tab.outerWidth() + 3;
                        if (tab_right <= full_width) {
                            continue;
                        }
                        if (!count_right) {
                            $tabs_scroller.data('next-right-tab', $all_tabs[j]);
                        }
                        count_right += 1;
                    };
                    $tabs_scroller.find('.scroll-right .badge').text(count_right);
                    if (!count_right) {
                        $tabs_scroller.data('next-right-tab', null);
                    }
                }

                // toggle arrows visibility
                $tabs_scroller.toggleClass('no-scroll-left', !show_left_arrow)
                              .toggleClass('no-scroll-right', !show_right_arrow);

            }

        }), // scroll_tabs

        scroll_tabs_left: (function IssueDetail__scroll_tabs_left (ev) {
            var $node = $(ev.target).closest('.issue-container'),
                $tabs_scroller = $node.find('.issue-tabs'),
                next_tab = $tabs_scroller.data('next-left-tab');
            if (next_tab) {
                IssueDetail.scroll_tabs($node, false, $(next_tab));
            }
            return false;
        }), // scroll_tabs_left

        scroll_tabs_right: (function IssueDetail__scroll_tabs_right (ev) {
            var $node = $(ev.target).closest('.issue-container'),
                $tabs_scroller = $node.find('.issue-tabs'),
                next_tab = $tabs_scroller.data('next-right-tab');
            if (next_tab) {
                IssueDetail.scroll_tabs($node, false, $(next_tab));
            }
            return false;
        }), // scroll_tabs_right

        load_tab: (function IssueDetail__load_tab (ev) {
            var $tab = $(ev.target),
                $tab_pane = $($tab.attr('href')),
                tab_type = $tab_pane.data('tab'),
                is_code_tab = $tab_pane.hasClass('code-files'),
                is_review_tab = $tab_pane.hasClass('issue-review'),
                $node = $tab.closest('.issue-container'),
                is_empty = !!$tab_pane.children('.empty-area').length;

            // load content if not already available
            if (is_empty) {
                $.ajax({
                    url: $tab_pane.data('url'),
                    success: function(data) {
                        $tab_pane.html(data);
                        // adjust tabs if scrollbar
                        IssueDetail.scroll_tabs($node);
                        if (is_code_tab) {
                            IssueDetail.on_files_list_loaded($node, $tab_pane);
                        }
                        if (is_review_tab) {
                            IssueDetail.on_review_loaded($node, $tab_pane);
                        }
                        $node.trigger('loaded.tab.' + tab_type);
                    },
                    error: function() {
                        $tab_pane.children('.empty-area').html('Loading failed :(');
                    }
                });
            } else {
                if (is_code_tab) {
                    IssueDetail.on_files_list_loaded($node, $tab_pane);
                }
                if (is_review_tab) {
                    IssueDetail.on_review_loaded($node, $tab_pane);
                }
            }

            // make sure the active tab is fully visible
            IssueDetail.scroll_tabs($node);

            // if the tabs holder is stuck, we'll scroll in a cool way
            var $tabs_holder = $node.find('.issue-tabs'),
                $stuck_header, position, $stuck,
                is_modal = IssueDetail.is_modal($node),
                $context = IssueDetail.get_scroll_context($node, is_modal),
                scroll_position = $tab_pane.data('scroll-position');
            if (scroll_position) {
                $context.scrollTop(scroll_position);
            } else if ($tabs_holder.hasClass('stuck')) {
                $stuck_header = $node.find(' > article > .area-top header');
                position = $node.find('.tab-content').position().top
                         + (is_modal ? 0 : $context.scrollTop())
                         - $stuck_header.height()
                         - $tabs_holder.height()
                         - 3 // adjust
                $context.scrollTop(Math.round(0.5 + position));
            }
            if (is_code_tab) {
                // seems to be a problem with waypoints on many files-list-containers
                $.waypoints('refresh');
            }
            if (!is_empty) {
                $node.trigger('loaded.tab.' + tab_type);
            }
        }), // load_tab

        close_tab: (function IssueDetail__close_tab (ev) {
            var $tab = $(ev.target).closest('li'),
                $tab_link = $tab.children('a'),
                $tab_pane = $($tab_link.attr('href')),
                is_active = $tab.hasClass('active'),
                $prev_tab = is_active ? $tab.prev(':visible').children('a') : null,
                $node = is_active ? null : $tab.closest('.issue-container');

            $tab.remove();
            if ($prev_tab) {
                $prev_tab.tab('show');
            } else {
                IssueDetail.scroll_tabs($node, true);
            }
            // we can only remove files tabs (commits)
            IssueDetail.unset_tab_files_waypoints($tab_pane);
            $tab_pane.remove();

            return false;
        }), // close_tab

        on_current_panel_key_event: (function IssueDetail__on_current_panel_key_event (method) {
            var decorator = function(e) {
                if (!PanelsSwpr.current_panel || PanelsSwpr.current_panel.obj != IssueDetail) { return; }
                return IssueDetail[method](PanelsSwpr.current_panel);
            };
            return Ev.key_decorate(decorator);
        }), // on_current_panel_key_event

        is_modal_an_IssueDetail: (function IssueDetail__is_modal_an_IssueDetail ($modal) {
            var panel = PanelsSwpr.current_panel;
            if (!panel || panel.obj != IssueDetail) { return false; }
            if (!IssueDetail.is_modal(panel.$node)) { return false; }
            return  (panel.$node.data('$modal')[0] == $modal[0]);
        }), // is_modal_an_IssueDetail

        on_main_issue_panel_key_event: (function IssueDetail__on_main_issue_panel_key_event (method) {
            var decorator = function(e) {
                if (!IssueDetail.$main_container.length) { return; }
                PanelsSwpr.select_panel_from_node(IssueDetail.$main_container);
                return IssueDetail[method](PanelsSwpr.current_panel);
            };
            return Ev.key_decorate(decorator);
        }), // on_main_issue_panel_key_event

        on_panel_activated: (function IssueDetail__on_panel_activated (panel) {
            if (IssuesList.current) {
                IssuesList.current.unset_current();
            }
            panel.$node.focus();
        }), // on_panel_activated

        panel_activable: (function IssueDetail__panel_activable (panel) {
            if (!panel) { return false; }
            if (IssueDetail.is_modal(panel.$node)) {
                return panel.$node.data('$modal').hasClass('in');
            }
            if (!panel.$node.children('.issue-nav').length) {
                return false;
            }
            return true;
        }), // panel_activable

        on_modal_shown: (function IssueDetail__on_modal_show () {
            var $modal = $(this);
            if (PanelsSwpr.current_panel.$node == $modal.data('$container')) {
                return;
            }
            $modal.data('previous-panel', PanelsSwpr.current_panel);
            PanelsSwpr.select_panel_from_node($modal.data('$container'));
        }), // on_modal_show

        on_modal_hidden: (function IssueDetail__on_modal_hidden () {
            var $modal = $(this);
            IssueDetail.unset_issue_waypoints($modal.find('.issue-container'));
            PanelsSwpr.select_panel($modal.data('previous-panel'));
            $modal.data('$container').html('');
        }), // on_modal_hidden

        on_files_list_key_event:  (function IssueDetail__on_files_list_key_event (method) {
            var decorator = function(e) {
                if (PanelsSwpr.current_panel.obj != IssueDetail) { return; }
                var $node = PanelsSwpr.current_panel.$node,
                    $tab = $node.find('.files-tab.active');
                if (!$tab.length) { return; }
                return IssueDetail[method].call($tab);
            };
            return Ev.key_decorate(decorator);
        }), // on_files_list_key_event

        on_review_key_event:  (function IssueDetail__on_review_key_event (method) {
            var decorator = function(e) {
                if (PanelsSwpr.current_panel.obj != IssueDetail) { return; }
                var $node = PanelsSwpr.current_panel.$node,
                    $tab = $node.find('.pr-review-tab.active');
                if (!$tab.length) { return; }
                return IssueDetail[method].call($tab);
            };
            return Ev.key_decorate(decorator);
        }), // on_review_key_event

        focus_search_input: (function IssueDetail__focus_search_input () {
            var $node = $(this).closest('.issue-container'),
                $tab_pane = $node.find('.tab-pane.active'),
                $files_list_container = $tab_pane.find('.code-files-list-container'),
                $search_input = $files_list_container.find('input.quicksearch');
            $search_input.focus();
            return false;
        }), // focus_search_input

        toggle_full_screen: (function IssueDetail__toggle_full_screen (panel) {
            panel.$node.toggleClass('big-issue');
            IssueDetail.scroll_tabs(panel.$node, true);
            return false;
        }), // toggle_full_screen

        view_on_github: (function IssueDetail__view_on_github (panel) {
            var $link = panel.$node.find('header h3 a').first();
            if ($link.length) {
                window.open($link.attr('href'), '_blank');
            }
            return false;
        }), // view_on_github

        refresh: (function IssueDetail__refresh (panel) {
            var issue_ident = IssueDetail.get_issue_ident(panel.$node),
                is_popup = IssueDetail.is_modal(panel.$node);
            IssuesListIssue.open_issue(issue_ident, is_popup, true);
            return false;
        }), // refresh

        force_refresh: (function IssueDetail__force_refresh (panel) {
            var issue_ident = IssueDetail.get_issue_ident(panel.$node),
                number = issue_ident.number.toString();
            if (number.indexOf('pk-') == -1) {
                $.ajax({
                    url: '/' + issue_ident.repository + '/issues/ask-fetch/' + number + '/',
                    type: 'POST',
                    headers: {
                        'X-CSRFToken': $body.data('csrf'),
                    }
                })
            }
            return false;
        }), // force_refresh

        on_link_to_diff_comment: (function IssueDetail__on_link_to_diff_comment () {
            var $link = $(this),
                url = $link.closest('.issue-comment').data('url'),
                $node = $link.closest('.issue-container');
            $node.one('loaded.tab.issue-files', function() {
                var $tab_pane = $node.find('.tab-pane.active'),
                    $comment_node = $node.find('.issue-files .issue-comment[data-url="' + url + '"]');
                if ($comment_node.length) {
                    var relative_position = -20;  // some margin
                    if (IssueDetail.is_modal($node)) {
                        var $container = $comment_node.closest('.code-comments');
                        relative_position += $container.position().top;
                    }
                    IssueDetail.scroll_in_files_list($node, $tab_pane, $comment_node, relative_position);
                } else {
                    alert('This comment is not linked to active code anymore');
                }
            });
            IssueDetail.select_files_tab(PanelsSwpr.current_panel);
        }), // on_link_to_diff_comment

        on_link_to_review_comment: (function IssueDetail__on_link_to_review_comment () {
            var $button = $(this),
                css_filter = $.map($button.data('ids'), function(id) { return '.issue-review [data-id=' + id + ']' } ).join(', '),
                $node = $button.closest('.issue-container');
            $node.one('loaded.tab.issue-review', function() {
                var $comment_node = $node.find(css_filter).first();
                if (!$comment_node.length) {
                    alert('This comment was not found, maybe a bug ;)');
                    return;
                }
                var do_scroll = function() {
                    var $tab_pane = $node.find('.tab-pane.active'),
                        relative_position = -20; // some margin
                    IssueDetail.mark_current_review_comment($tab_pane, $comment_node);
                    if (IssueDetail.is_modal($node)) {
                        var $container = $comment_node.closest('.code-comments');
                        relative_position += $container.position().top;
                    }
                    IssueDetail.scroll_in_review($node, $tab_pane, $comment_node, relative_position);

                }; // do_scroll
                var $container = $comment_node.closest('.collapse');
                if (!$container.hasClass('in')) {
                    $container.one('shown.collapse', do_scroll);
                    $container.collapse('show');
                } else {
                   do_scroll();
                }
            });
            IssueDetail.select_review_tab(PanelsSwpr.current_panel);
        }), // on_link_to_review_comment

        on_deleted_commits_toggle_change: (function IssueDetail__on_deleted_commits_toggle_change () {
            var $input = $(this),
                $parent = $input.closest('.issue-commits');
                $parent.toggleClass('view-deleted', $input.is(':checked'))
        }), // on_deleted_commits_toggle_change

        on_commit_click: (function IssueDetail__on_commit_click (e) {
            var $link = $(e.target),
                $holder = $link.closest('.commit-link-holder'),
                repository, sha, url,
                nb_files, nb_comments, $label_node,
                $node, tab_name;


            if (!$holder.length) {
                return;
            }

            repository = $holder.data('repository');
            $node = $holder.closest('.issue-container');

            if (repository != $node.data('repository')) {
                return;
            }

            sha = $holder.data('sha');
            tab_name = 'commit-' + sha;

            // if the tab does not exists, create it
            if (!$node.find('.' + tab_name + '-tab').length) {
                var $tab_template = $node.find('.commit-tab.template'),
                    $tab = $tab_template.clone(),
                    $tab_pane_template = $node.find('.commit-files.template'),
                    $tab_pane = $tab_pane_template.clone();

                // prepare the tab
                $tab.removeClass('template')
                    .addClass(tab_name + '-tab')
                    .attr('style', null);

                $tab.find('a').attr('href', '#' + tab_name + '-files');
                $tab.find('strong').text(sha.substring(0, 7));

                nb_files = parseInt($holder.data('files-count'), 10);
                $label_node = $tab.find('.fa-file-o');
                $label_node.next().text(nb_files);
                $label_node.parent().attr('title', nb_files + ' changed file' + (nb_files > 1 ? 's' : '' ));

                nb_comments = $holder.data('comments-count');
                $label_node = $tab.find('.fa-comments-o');
                if (nb_comments) {
                    $label_node.next().text(nb_comments);
                    $label_node.parent().attr('title', nb_comments + ' comment' + (nb_comments > 1 ? 's' : '' ));
                } else {
                    $label_node.parent().remove();
                }

                // add the tab
                $tab.insertBefore($tab_template);

                // prepare the content
                $tab_pane.removeClass('template')
                        .addClass(tab_name)
                        .attr('id', tab_name + '-files')
                        .attr('style', null)
                        .data('url', $holder.data('url'))
                        .data('comment-url', $holder.data('comment-url'));

                // add the content
                $tab_pane.insertBefore($tab_pane_template);

            }

            IssueDetail.select_tab(PanelsSwpr.current_panel, tab_name);

            return false;

        }), // on_commit_click

        init: (function IssueDetail__init () {
            // init modal container
            IssueDetail.$modal_body = IssueDetail.$modal.children('.modal-body'),
            IssueDetail.$modal_container = IssueDetail.$modal_body.children('.issue-container'),
            IssueDetail.$modal_container.data('$modal', IssueDetail.$modal);
            IssueDetail.$modal.data('$container', IssueDetail.$modal_container);

            // full screen mode
            jwerty.key('s', IssueDetail.on_current_panel_key_event('toggle_full_screen'));
            jwerty.key('s', IssueDetail.on_main_issue_panel_key_event('toggle_full_screen'));
            $document.on('click', '.resize-issue', Ev.stop_event_decorate_dropdown(toggle_full_screen_for_current_modal));
            $document.on('click', '.resize-issue', IssueDetail.on_current_panel_key_event('toggle_full_screen'));

            jwerty.key('v', IssueDetail.on_current_panel_key_event('view_on_github'));
            jwerty.key('v', IssueDetail.on_main_issue_panel_key_event('view_on_github'));

            jwerty.key('r', IssueDetail.on_current_panel_key_event('refresh'));
            jwerty.key('r', IssueDetail.on_main_issue_panel_key_event('refresh'));
            $document.on('click', '.refresh-issue', Ev.stop_event_decorate_dropdown(IssueDetail.on_current_panel_key_event('refresh')));

            jwerty.key('shift+g', IssueDetail.on_current_panel_key_event('force_refresh'));
            jwerty.key('shift+g', IssueDetail.on_main_issue_panel_key_event('force_refresh'));
            $document.on('click', '.force-refresh-issue', Ev.stop_event_decorate_dropdown(IssueDetail.on_current_panel_key_event('force_refresh')));

            // tabs activation
            jwerty.key('shift+d', IssueDetail.on_current_panel_key_event('select_discussion_tab'));
            jwerty.key('shift+c', IssueDetail.on_current_panel_key_event('select_commits_tab'));
            jwerty.key('shift+f', IssueDetail.on_current_panel_key_event('select_files_tab'));
            jwerty.key('shift+r', IssueDetail.on_current_panel_key_event('select_review_tab'));
            $document.on('show.tab', '.issue-tabs a', IssueDetail.before_load_tab);
            $document.on('shown.tab', '.issue-tabs a', IssueDetail.load_tab);

            $document.on('click', '.issue-tabs:not(.no-scroll-left) .scroll-left', Ev.stop_event_decorate(IssueDetail.scroll_tabs_left));
            $document.on('click', '.issue-tabs:not(.no-scroll-right) .scroll-right', Ev.stop_event_decorate(IssueDetail.scroll_tabs_right));

            $document.on('click', '.issue-tabs .closable i.fa-times', Ev.stop_event_decorate(IssueDetail.close_tab));

            // link from PR comment in "review" tab to same entry in "files changed" tab
            $document.on('click', '.go-to-diff-link', Ev.stop_event_decorate(IssueDetail.on_link_to_diff_comment));

            // link from PR comment group in "discussion" tab to first entry "files changed" tab
            $document.on('click', '.go-to-review-link', Ev.stop_event_decorate(IssueDetail.on_link_to_review_comment));

            // modal events
            if (IssueDetail.$modal.length) {
                IssueDetail.$modal.on('shown.modal', IssueDetail.on_modal_shown);
                IssueDetail.$modal.on('hidden.modal', IssueDetail.on_modal_hidden);
            }

            // waypoints for loaded issue
            if (IssueDetail.$main_container.data('number')) {
                IssueDetail.on_issue_loaded(IssueDetail.$main_container, false);
            }

            // commits options
            $document.on('change', '.deleted-commits-toggler input', IssueDetail.on_deleted_commits_toggle_change);
            $document.on('click', '.commit-link', Ev.stop_event_decorate(IssueDetail.on_commit_click));

            // files list summary
            $document.on('click', '.code-files-list a', Ev.stop_event_decorate(IssueDetail.on_files_list_click));
            $document.on('shown.collapse hidden.collapse', '.code-files-list', IssueDetail.on_files_list_toggle);
            $document.on('mouseenter', '.code-file', IssueDetail.on_file_mouseenter);
            jwerty.key('f', IssueDetail.on_files_list_key_event('focus_search_input'));
            jwerty.key('t', IssueDetail.on_files_list_key_event('toggle_files_list'));
            // files list navigation
            $document.on('click', 'li:not(.disabled) a.go-to-previous-file', Ev.stop_event_decorate(IssueDetail.go_to_previous_file));
            $document.on('click', 'li:not(.disabled) a.go-to-next-file', Ev.stop_event_decorate(IssueDetail.go_to_next_file));
            $document.on('quicksearch.after', '.files-filter input.quicksearch', IssueDetail.on_files_filter_done);
            $document.on('click', 'li:not(.disabled) a.go-to-previous-file-comment', Ev.stop_event_decorate(IssueDetail.go_to_previous_file_comment));
            $document.on('click', 'li:not(.disabled) a.go-to-next-file-comment', Ev.stop_event_decorate(IssueDetail.go_to_next_file_comment));
            $document.on('click', '.go-to-global-comments', Ev.stop_event_decorate_dropdown(IssueDetail.go_to_global_comments, '.btn-group'));
            jwerty.key('p/k', IssueDetail.on_files_list_key_event('go_to_previous_file'));
            jwerty.key('n/j', IssueDetail.on_files_list_key_event('go_to_next_file'));
            jwerty.key('shift+p/shift+k', IssueDetail.on_files_list_key_event('go_to_previous_file_comment'));
            jwerty.key('shift+n/shift+j', IssueDetail.on_files_list_key_event('go_to_next_file_comment'));


            // review navigation
            $document.on('click', 'li:not(.disabled) a.go-to-previous-review-comment', Ev.stop_event_decorate(IssueDetail.go_to_previous_review_comment));
            $document.on('click', 'li:not(.disabled) a.go-to-next-review-comment', Ev.stop_event_decorate(IssueDetail.go_to_next_review_comment));
            jwerty.key('p/k/shift+p/shift+k', IssueDetail.on_review_key_event('go_to_previous_review_comment'));
            jwerty.key('n/j/shift+n/shift+j', IssueDetail.on_review_key_event('go_to_next_review_comment'));
        }) // init
    }; // IssueDetail
    IssueDetail.init();

    IssuesList.prototype.on_panel_activated = (function IssuesList__on_panel_activated (panel) {
        this.set_current();
    });

    /*
        Code to pass focus from panel to panel
    */
    var PanelsSwpr = {
        events: 'click focus',
        panels: [],
        current_panel: null,
        add_handler: (function PanelsSwpr__add_handler (panel) {
            panel.$node.on(PanelsSwpr.events, {panel: panel}, PanelsSwpr.on_event);
        }), // add_handler
        remove_handler: (function PanelsSwpr__remove_handler (panel) {
            panel.$node.off(PanelsSwpr.events, PanelsSwpr.on_event);
        }), // remove_handler
        on_event: (function PanelsSwpr__on_event (ev) {
            PanelsSwpr.select_panel(ev.data.panel, ev);
        }), // on_event
        panel_activable: (function PanelsSwpr__panel_activable (panel) {
            return (panel && (!panel.obj.panel_activable || panel.obj.panel_activable(panel)));
        }), // panel_activable
        select_panel_from_node: (function PanelsSwpr__select_panel_from_node ($node) {
            for (var i = 0; i < PanelsSwpr.panels.length; i++) {
                if (PanelsSwpr.panels[i].$node == $node) {
                    PanelsSwpr.select_panel(PanelsSwpr.panels[i]);
                    return;
                }
            }
        }), // select_panel_from_node
        select_panel: (function PanelsSwpr__select_panel (panel, ev) {
            if (!panel || !PanelsSwpr.panel_activable(panel)) { return; }
            if (panel.handlable) { PanelsSwpr.remove_handler(panel); }
            var old_panel = PanelsSwpr.current_panel;
            PanelsSwpr.current_panel = panel;
            if (old_panel.handlable) { PanelsSwpr.add_handler(old_panel); }
            $('.active-panel').removeClass('active-panel');
            PanelsSwpr.current_panel.$node.addClass('active-panel');
            PanelsSwpr.current_panel.obj.on_panel_activated(PanelsSwpr.current_panel);
            return true;
        }), // select_panel
        go_prev_panel: (function PanelsSwpr__go_prev_panel(ev) {
            if (!PanelsSwpr.current_panel.handlable) { return }
            var idx = PanelsSwpr.current_panel.index;
            if (idx > 0) {
                PanelsSwpr.select_panel(PanelsSwpr.panels[idx - 1]);
            }
        }), // go_prev_panel
        go_next_panel: (function PanelsSwpr__go_next_panel(ev) {
            if (!PanelsSwpr.current_panel.handlable) { return }
            var idx = PanelsSwpr.current_panel.index;
            if (idx < PanelsSwpr.panels.length - 1) {
                PanelsSwpr.select_panel(PanelsSwpr.panels[idx + 1]);
            }
        }), // go_next_panel
        init: (function PanelsSwpr__init (panels) {
            PanelsSwpr.panels = panels;
            if (panels.length) {
                PanelsSwpr.current_panel = panels[0];
                PanelsSwpr.current_panel.$node.addClass('active-panel');
                for (var i = 0; i < panels.length; i++) {
                    panels[i].index = i;
                    if (panels[i].handlable && i != PanelsSwpr.current_panel.index) {
                        PanelsSwpr.add_handler(panels[i]);
                    }
                };
                jwerty.key('ctrl+←', Ev.key_decorate(PanelsSwpr.go_prev_panel));
                jwerty.key('ctrl+→', Ev.key_decorate(PanelsSwpr.go_next_panel));
            }
        }) // init

    }; // PanelsSwpr

    // add all issues lists
    (function() {
        var panels = [];
        for (var i = 0; i < IssuesList.all.length; i++) {
            var issues_list = IssuesList.all[i];
            panels.push({$node: issues_list.$node.parent(), obj: issues_list, handlable: true});
        };
        // add the main issue detail if exists
        if (IssueDetail.$main_container.length) {
            panels.push({$node: IssueDetail.$main_container, obj: IssueDetail, handlable: true});
        }
        // add the popup issue detail if exists
        if (IssueDetail.$modal_container.length) {
            panels.push({$node: IssueDetail.$modal_container, obj: IssueDetail, handlable: false});
        }
        PanelsSwpr.init(panels);
        window.PanelsSwpr = PanelsSwpr;
    })();


    // select the issue given in the url's hash, or an active one in the html,
    // or the first item of the current list
    if (IssuesList.all.length) {
        IssuesList.all[0].set_current();
        var issue_to_select = null;
        if (location.hash && /^#issue\-\d+$/.test(location.hash)) {
            issue_to_select = $(location.hash);
        } else if ((issue_to_select=/\/issues\/(\d+)\/$/.exec(location.pathname)) && issue_to_select.length == 2) {
            issue_to_select = $('#issue-' + issue_to_select[1]);
        } else {
            issue_to_select = $(IssuesListIssue.selector + '.active');
        }
        if (issue_to_select && issue_to_select.length && issue_to_select[0].IssuesListIssue) {
           issue_to_select.removeClass('active');
           issue_to_select[0].IssuesListIssue.set_current(true);
        } else {
            IssuesList.current.go_to_next_item();
        }
    }

    var activate_quicksearches = (function activate_quicksearches ($inputs) {
        $inputs.each(function() {
            var $input, target, content, content_data, options, qs;
            $input = $(this);
            if (!$input.data('quicksearch')) {
                target = $input.data('target');
                if (!target) { return; }

                options = {
                    bind: 'keyup quicksearch.refresh',
                    show: function () {
                        this.style.display = "";
                        $(this).removeClass('hidden');
                    },
                    hide: function() {
                        this.style.display = "none";
                        $(this).addClass('hidden');
                    },
                    onBefore: function() {
                        $input.trigger('quicksearch.before');
                    },
                    onAfter: function() {
                        $input.trigger('quicksearch.after');
                    }
                };

                content = $input.data('content');
                if (content) {
                    options.selector = content;
                }
                content_data = $input.data('content-data');
                if (content_data) {
                    options.selector_data = content_data;
                }

                qs = $input.quicksearch(target, options);
                $input.data('quicksearch', qs);

                var clear_input = function(e) {
                    $input.val('');
                    $input.trigger('quicksearch.refresh');
                    $input.focus();
                    e.stopPropagation();
                    e.preventDefault();
                    return false;
                };
                $input.on('keydown', jwerty.event('ctrl+u', clear_input));

                var clear_btn = $input.next('.btn');
                if (clear_btn.length) {
                    clear_btn.on('click', clear_input);
                    clear_btn.on('keyup', jwerty.event('space', clear_input));
                }
            }
        });
    }); // activate_quicksearches
    window.activate_quicksearches = activate_quicksearches;
    activate_quicksearches($('input.quicksearch'));

    if ($().deferrable) {
        $('.deferrable').deferrable();
    }

    var FilterManager = {
        ARGS: Arg.all(),
        CACHE: {},
        selector: 'a.js-filter-trigger',
        user_search: /^(.+\/)(created_by|assigned|closed_by)\/(.+)\/$/,
        messages: {
            pr: {
                'on': 'Click to display only pull requests',
                'off': 'Click to stop displaying only pull requests'
            },
            milestone: {
                'on': 'Click to filter on this milestone',
                'off': 'Click to stop filtering on this milestone'
            },
            labels: {
                'on': 'Click to filter on this ',
                'off': 'Click to stop filtering on this ',
            },
            assigned: {
                'on': 'Click to filter issues assigned to him',
                'off': 'Click to stop filtering issues assigned to him',
            },
            created_by: {
                'on': 'Click to filter issues created by him',
                'off': 'Click to stop filtering issues created by him',
            },
            closed_by: {
                'on': 'Click to filter issues closed by him',
                'off': 'Click to stop filtering issues closed by him',
            }
        }, // messages
        block_empty_links: function(ev) {
            if ($(this).is(FilterManager.selector)) {
                ev.stopPropagation();
                ev.preventDefault();
            }
        },
        update: function() {
            var $link = $(this),
                filter = $link.data('filter'),
                href, title;
            if (typeof FilterManager.CACHE[filter] === 'undefined') {
                var parts = filter.split(':'),
                    key = parts.shift(),
                    value = parts.join(':'),
                    args = $.extend({}, FilterManager.ARGS),
                    message_type;
                switch(key) {
                    case 'pr':
                    case 'milestone':
                        if (typeof args[key] === 'undefined' || args[key] != value) {
                            args[key] = value;
                            message_type = 'on';
                        } else {
                            delete args[key];
                            message_type = 'off';
                        }
                        title = FilterManager.messages[key][message_type];
                        href = Arg.url(args);
                        break;
                    case 'labels':
                        var labels = (args[key] || '').split(','),
                            pos = labels.indexOf(value),
                            final_labels = [];
                        if (pos >= 0) {
                            labels.splice(pos, 1);
                        } else {
                            labels.push(value);
                        }
                        for (var i = 0; i < labels.length; i++) {
                            if (labels[i]) { final_labels.push(labels[i]); }
                        }
                        if (final_labels.length) {
                            args[key] = final_labels.join(',');
                            message_type = 'on';
                        } else {
                            delete args[key];
                            message_type = 'off';
                        }
                        title = FilterManager.messages[key][message_type] + ($link.data('type-name') || 'label');
                        href = Arg.url(args);
                        break;
                    case 'created_by':
                    case 'assigned':
                    case 'closed_by':
                        var path = location.pathname,
                            matches = path.match(FilterManager.user_search),
                            to_add = true;
                        if (matches) {
                            if (matches[2] == key && matches[3] == value) {
                                to_add = false;
                            }
                            path = matches[1];
                        }
                        message_type = 'off';
                        if (to_add) {
                            path = path + key + '/' + value + '/';
                            message_type = 'on';
                        }
                        title = FilterManager.messages[key][message_type];
                        href = Arg.url(path, args);
                        break;
                };
                if (href) {
                    var orig_title = $link.attr('title') || '';
                    if (orig_title) { title = orig_title + '. ' + title};
                    FilterManager.CACHE[filter] = {href: href, title: title + '.'};
                }
            }
            if (typeof FilterManager.CACHE[filter] !== 'undefined') {
                $link.attr('href', FilterManager.CACHE[filter].href)
                     .attr('title', FilterManager.CACHE[filter].title)
                     .removeClass('js-filter-trigger');
            }
        }, // update
        init: function() {
            $(FilterManager.selector)
                .on('click', FilterManager.block_empty_links)
                .each(FilterManager.update);
            FilterManager.CACHE = {};  // reset cache for memory
        } // init
    }; // FilterManager
    FilterManager.init();

    var MarkdownManager = {
        re: new RegExp('https?://github.com/([\\w\\-\\.]+/[\\w\\-\\.]+)/(?:issue|pull)s?/(\\d+)'),
        toggle_email_reply: function() {
            var $reply = $(this).parent().next('.email-hidden-reply');
            if (!$reply.hasClass('collapse')) {
                $reply.addClass('collapse').show();
            }
            $reply.collapse('toggle');
            return false;
        }, // toggle_email_reply
        activate_email_reply_toggle: function() {
            $document.on('click', '.email-hidden-toggle a', MarkdownManager.toggle_email_reply);
        }, // activate_email_reply_toggle
        update_link: function(link, repository) {
            link.setAttribute('data-managed', 1);
            var $link = $(link);
            $link.attr('target', '_blank');
            var matches = link.href.match(MarkdownManager.re);
            // handle link only if current repository
            if (matches && (matches[1] == repository || matches[1] == main_repository)) {
                $link.data('repository', matches[1])
                     .data('number', matches[2])
                     .addClass('issue-link');
            }
        }, // update_link
        update_links: function() {
            $('.issue-container').each(function() {
                var $container = $(this),
                    repository = $container.data('repository');
                $container.find('.issue-body, .issue-comment .content')
                          .find('a:not([data-managed])')
                          .each(function() {
                                MarkdownManager.update_link(this, repository);
                            });
            });
        }, // update_links
        handle_issue_link: function(ev) {
            var $link = $(this),
                issue_ident = {
                    number: $link.data('number'),
                    repository: $link.data('repository')
                };
            if (!issue_ident.repository || ! issue_ident.number) { return; }
            ev.stopPropagation();
            ev.preventDefault();
            IssuesListIssue.open_issue(issue_ident, true);
            return false;
        }, // handle_issue_link
        handle_issue_links: function() {
            $document.on('click', '.issue-container a.issue-link', MarkdownManager.handle_issue_link);
        }, // handle_issue_links
        init: function() {
            MarkdownManager.activate_email_reply_toggle();
            MarkdownManager.update_links();
            MarkdownManager.handle_issue_links();
        } // init
    }; // MarkdownManager
    MarkdownManager.init();


    var MessagesManager = {

        extract: (function MessagesManager__extract (html) {
            // Will extrat message from ajax requests to put them
            // on the main messages container
            var $fake_node = $('<div />');
            $fake_node.html(html);
            var $new_messages = $fake_node.find('#messages');
            if ($new_messages.length) {
                $new_messages.remove();
                var $messages = $('#messages');
                if ($messages.length) {
                    $messages.append($new_messages.children());
                } else {
                    $body.children('header:first-of-type').after($new_messages);
                }
                MessagesManager.init_auto_hide();
                return $fake_node.html();
            } else {
                return html;
            }
        }), // extract

        first_message: (function MessagesManager__first_message () {
            return $('#messages').children('li.alert').first();
        }), // first_message

        hide_delays: {
            1: 4000,
            2: 2000,
            3: 1500,
            4: 1250,
            'others': 1000,
        },

        hide_delay: (function MessagesManager__hide_delay () {
            var count = $('#messages').children('li.alert').length;
            return MessagesManager.hide_delays[count] || MessagesManager.hide_delays.others;
        }), // count_messages

        auto_hide_timer: null,
        init_auto_hide: (function MessagesManager__init_auto_hide () {
            if (MessagesManager.auto_hide_timer) {
                clearTimeout(MessagesManager.auto_hide_timer);
                MessagesManager.auto_hide_timer = null;
            }
            var $first = MessagesManager.first_message();
            if (!$first.length) { return; }
            MessagesManager.auto_hide_timer = setTimeout(MessagesManager.auto_hide_first, MessagesManager.hide_delay());
        }), // init_auto_hide

        auto_hide_first: (function MessagesManager__auto_hide_first () {
            MessagesManager.first_message().fadeOut('slow', MessagesManager.remove_first);
        }), // auto_hide_first

        remove_first: (function MessagesManager__remove_first () {
            $(this).remove();
            MessagesManager.auto_hide_timer = null;
            MessagesManager.init_auto_hide();
        }) // remove_first

    }; // MessagesManager

    $.ajaxSetup({
        converters: {
            "text html": MessagesManager.extract
        } // converts
    }); // ajaxSetup
    MessagesManager.init_auto_hide();

    var IssueEditor = {
        disable_form: (function IssueEditor__disable_form ($form) {
            // disabled input will be ignored by serialize, so just set them
            // readonly
            $form.find(':input').prop('readonly', true);
            $form.find(':button').prop('disabled', true);
            if (typeof $().select2 != 'undefined') {
                $form.find('select.select2-offscreen').select2('readonly', true);
            }
            $form.data('disabled', true);
        }), // disable_form

        enable_form: (function IssueEditor__enable_form ($form) {
            $form.find(':input').prop('readonly', false);
            $form.find(':button').prop('disabled', false);
            if (typeof $().select2 != 'undefined') {
                $form.find('select.select2-offscreen').select2('readonly', false);
            }
            $form.data('disabled', false);
        }), // enable_form

        focus_form: (function IssueEditor__focus_form ($form, delay) {
            if (delay) {
                setTimeout(function() { IssueEditor.focus_form($form); }, delay)
            } else {
                $form.find(':input:visible:not([type=submit])').first().focus();
            }
        }), // focus_form

        display_issue: (function IssueEditor__display_issue (html, context, force_popup) {
            var is_popup = force_popup || context.$node.parents('.modal').length > 0;
                container = IssueDetail.get_container(is_popup);
            IssueDetail.set_container_loading(container);
            IssueDetail.display_issue(html, context.issue_ident, is_popup);
        }), // display_issue

        get_form_context: (function IssueEditor__get_form_context ($form) {
            var $node = $form.closest('.issue-container'),
            context = {
                issue_ident: IssueDetail.get_issue_ident($node),
                $form: $form,
                $node: $node
            };
            return context;
        }), // get_form_context

        handle_form: (function IssueEditor__handle_form ($form, ev) {
            ev.preventDefault();
            ev.stopPropagation();
            if ($form.data('disabled')) { return false; }
            IssueEditor.disable_form($form);
            var context = IssueEditor.get_form_context($form),
                $alert = $form.find('.alert');
            $form.find('button').addClass('loading');
            if ($alert.length) { $alert.remove(); }
            return context;
        }), // handle_form

        post_form: (function IssueEditor__post_form($form, context, on_done, on_failed, data, action) {
            if (typeof data == 'undefined') { data = $form.serialize(); }
            if (typeof action == 'undefined') { action = $form.attr('action'); }
            $.post(action, data)
                .done($.proxy(on_done, context))
                .fail($.proxy(on_failed, context));
        }), // post_form

        /* CHANGE ISSUE STATE */
        on_state_submit: (function IssueEditor__on_state_submit (ev) {
            var $form = $(this),
                context = IssueEditor.handle_form($form, ev);
            if (context === false) { return false; }

            IssueEditor.post_form($form, context, IssueEditor.on_state_submit_done,
                                                  IssueEditor.on_state_submit_failed);
        }), // on_state_submit

        on_state_submit_done: (function IssueEditor__on_state_submit_done (data) {
            this.$form.find('button').removeClass('loading');
            if (data.trim()) {
                IssueEditor.display_issue(data, this);
            } else {
                IssueEditor.enable_form(this.$form);
                this.$form.find('button.loading').removeClass('loading');
            }
        }), // on_state_submit_done

        on_state_submit_failed: (function IssueEditor__on_state_submit_failed () {
            IssueEditor.enable_form(this.$form);
            this.$form.find('button').removeClass('loading');
            alert('A problem prevented us to do your action !');
        }), // on_state_submit_failed

        /* POST COMMENT */
        on_comment_submit: (function IssueEditor__on_comment_submit (ev) {
            var $form = $(this),
                context = IssueEditor.handle_form($form, ev);
            if (context === false) { return false; }

            var $textarea = $form.find('textarea');

            if ($textarea.length && !$textarea.val().trim()) {
                $textarea.after('<div class="alert alert-error">You must enter a comment</div>');
                $form.find('button').removeClass('loading');
                IssueEditor.enable_form($form);
                $textarea.focus();
                return false;
            }

            IssueEditor.post_form($form, context, IssueEditor.on_comment_submit_done,
                                                  IssueEditor.on_comment_submit_failed);
        }), // on_comment_submit

        on_comment_submit_done: (function IssueEditor__on_comment_submit_done (data) {
            this.$form.closest('li').replaceWith(data);
        }), // on_comment_submit_done

        on_comment_submit_failed: (function IssueEditor__on_comment_submit_failed () {
            IssueEditor.enable_form(this.$form);
            this.$form.find('.alert').remove();
            var $textarea = this.$form.find('textarea');
            $textarea.after('<div class="alert alert-error">We were unable to post this comment</div>');
            this.$form.find('button').removeClass('loading');
            $textarea.focus();
        }), // on_comment_submit_failed

        on_comment_textarea_focus: (function IssueEditor__on_comment_textarea_focus () {
            $(this).addClass('focused');
        }), // on_comment_textarea_focus

        on_comment_edit_click: (function IssueEditor__on_comment_edit_click (ev) {
            var $link = $(this),
                $comment_node = $link.closest('li.issue-comment');
            if ($link.parent().hasClass('disabled')) { return false; }
            IssueEditor.disable_comment($comment_node, $link);
            $.get($link.attr('href'))
                .done($.proxy(IssueEditor.on_comment_edit_or_delete_loaded, {$comment_node: $comment_node}))
                .fail($.proxy(IssueEditor.on_comment_edit_or_delete_load_failed, {$comment_node: $comment_node, text: 'edit'}));
            return false;
        }), // on_comment_edit_click

        on_comment_delete_click: (function IssueEditor__on_comment_delete_click (ev) {
            var $link = $(this),
                $comment_node = $link.closest('li.issue-comment');
            if ($link.parent().hasClass('disabled')) { return false; }
            IssueEditor.disable_comment($comment_node, $link);
            $.get($link.attr('href'))
                .done($.proxy(IssueEditor.on_comment_edit_or_delete_loaded, {$comment_node: $comment_node}))
                .fail($.proxy(IssueEditor.on_comment_edit_or_delete_load_failed, {$comment_node: $comment_node, text: 'delete confirmation'}));
            return false;
        }), // on_comment_delete_click

        disable_comment: (function IssueEditor__disable_comment ($comment_node, $link) {
            $link.addClass('loading');
            $comment_node.find('.dropdown-menu li').addClass('disabled');
        }), // disable_comment

        on_comment_edit_or_delete_loaded: (function IssueEditor__on_comment_edit_or_delete_loaded (data) {
            this.$comment_node.replaceWith(data);
        }), // on_comment_edit_or_delete_loaded

        on_comment_edit_or_delete_load_failed: (function IssueEditor__on_comment_edit_or_delete_load_failed () {
            this.$comment_node.find('.dropdown-menu li.disabled').removeClass('disabled');
            this.$comment_node.find('a.btn-loading.loading').removeClass('loading');
            alert('Unable to load the ' + this.text + ' form!')
        }), // on_comment_edit_or_delete_load_failed

        // CREATE THE PR-COMMENT FORM
        on_comment_create_placeholder_click: (function IssueEditor__on_comment_create_placeholder_click (ev) {
            var $placeholder = $(this).parent(),
                $comment_box = IssueEditor.create_comment_form_from_template($placeholder, $placeholder.closest('.issue-container'));
            $comment_box.$form.prepend('<input type="hidden" name="entry_point_id" value="' + $placeholder.data('entry-point-id') + '"/>')
            $placeholder.after($comment_box.$node);
            $placeholder.hide();
            $comment_box.$textarea.focus();
        }), // on_comment_create_placeholder_click

        create_comment_form_from_template: (function IssueEditor__create_comment_form_from_template ($trigger, $issue) {
            var $template = $issue.find('.comment-create-container').first(),
                $node = $template.clone(),
                $form = $node.find('form'),
                $tab_pane = $trigger.closest('.tab-pane'),
                is_commit = $tab_pane.hasClass('commit-files'),
                action = is_commit ? $tab_pane.data('comment-url') : $form.data('pr-url'),
                $textarea;
            $node.removeClass('comment-create-container');
            $form.attr('action', action);
            $textarea = $form.find('textarea');
            $textarea.val('');
            return {$node: $node, $form: $form, $textarea: $textarea};
        }), // create_comment_form_from_template

        // CREATE A NEW ENTRY POINT
        on_new_entry_point_click: (function IssueEditor__on_new_entry_point_click (ev) {
            var $tr = $(this).closest('tr'),
                $table = $tr.closest('table'),
                is_last_line = $tr.is(':last-of-type'),
                $entry_point, $textarea, $new_table, path, sha, position, $issue, $box, $new_table_box;
            // check if already an entry-point
            if (is_last_line) {
                $entry_point = $tr.closest('.code-diff').next('.code-comments');
                if ($entry_point.length) {
                    // check if we already have a textarea
                    $textarea = $entry_point.find('textarea');
                    if ($textarea.length) {
                        $textarea.focus();
                    } else {
                        // no textarea, click on the button to create one
                        $entry_point.find('.comment-create-placeholder button').click();
                    }
                    return false;
                }
            }
            $issue = $table.closest('.issue-container');
            // we need to create an entry point
            path = $table.data('path');
            sha = $table.data('sha');
            position = $tr.data('position');
            if (!is_last_line) {
                // start by making room, by moving all next lines in a new table
                $new_table = $('<table><tbody/></table>').addClass($table[0].className);
                $new_table.data({path: path, sha: sha});
                $new_table.children('tbody').append($tr.nextAll('tr'));
                $new_table_box = $issue.find('.code-diff.template').clone().removeClass('template').removeAttr('style');
                $new_table_box.append($new_table);
                $table.parent().after($new_table_box);
            }
            // create a box for the entry-point
            $box = $issue.find('.code-comments.template').clone().removeClass('template').removeAttr('style');
            $comment_box = IssueEditor.create_comment_form_from_template($table, $issue);
            $comment_box.$form.prepend('<input type="hidden" name="path" value="' + path + '"/>' +
                                       '<input type="hidden" name="sha" value="' + sha + '"/>' +
                                       '<input type="hidden" name="position" value="' + position + '"/>');
            $box.find('ul').append($comment_box.$node);
            $table.parent().after($box);
            $comment_box.$textarea.focus();

        }), // on_new_entry_point_click

        // CANCEL COMMENTS
        on_comment_create_cancel_click: (function IssueEditor__on_comment_create_cancel_click (ev) {
            var $button = $(this),
                $li = $button.closest('li.issue-comment'),
                $form = $li.find('form');

            IssueEditor.disable_form($form);

            // it's an answer to a previous PR comment
            var $placeholder = $li.prev('.comment-create-placeholder');
            if ($placeholder.length) {
                $li.remove();
                $placeholder.show();
                return false;
            }

            // its a new pr entry point
            var $pr_parent = $li.parent().parent();
            if ($pr_parent.hasClass('code-comments')) {
                var $prev = $pr_parent.prev();
                var $next = $pr_parent.next();
                $pr_parent.remove();
                if ($next.length) {
                    // combine the two block
                    $prev.find('> table > tbody').append($next.find('> table > tbody > tr'));
                    $next.remove();
                }
                return false;
            }

            // its the bottom comment form
            $li.find('textarea').val('');
            IssueEditor.enable_form($form);
            return false;
        }), //on_comment_create_cancel_click

        on_comment_edit_or_delete_cancel_click: (function IssueEditor__on_comment_edit_or_delete_cancel_click (ev) {
            var $li = $(this).closest('li.issue-comment');

            IssueEditor.disable_form($li.find('form'));

            $.get($li.data('url'))
                .done(function(data) {
                    $li.replaceWith(data);
                })
                .fail(function() {
                    alert('Unable to retrieve the original comment')
                });
        }), // on_comment_edit_or_delete_cancel_click

        // EDIT ISSUES FIELDS, ONE BY ONE
        on_issue_edit_field_click: (function IssueEditor__on_issue_edit_field_click (ev) {
            var $link = $(this);
            if ($link.hasClass('loading')) { return false; }
            $link.addClass('loading');
            $.ajax({
                url: $link.attr('href'),
                type: 'GET',
                success: IssueEditor.on_issue_edit_field_ready,
                error: IssueEditor.on_issue_edit_field_ready_click_failed,
                context: $link
            });
            return false;
        }), // on_issue_edit_field_click

        on_issue_edit_field_ready_click_failed: (function IssueEditor__on_issue_edit_field_ready_click_failed () {
            var $link = this;
            $link.removeClass('loading');
             alert('A problem prevented us to do your action !');
        }), // on_issue_edit_field_ready_click_failed

        on_issue_edit_field_ready: (function IssueEditor__on_issue_edit_field_ready (data) {
            var $link = this;
            if (!data.trim()) {
                $link.removeClass('loading');
                return false;
            }
            var field = $link.data('field'), $form,
                $placeholder = $link.closest('article').find('.edit-place[data-field=' + field + ']'),
                method = 'issue_edit_' + field + '_insert_field_form';
            if (typeof IssueEditor[method] == 'undefined') {
                method = 'issue_edit_default_insert_field_form';
            }
            $form = IssueEditor[method]($link, $placeholder, data);
            method = 'issue_edit_' + field + '_field_prepare';
            if (typeof IssueEditor[method] != 'undefined') {
                IssueEditor[method]($form);
            }
        }), // on_issue_edit_field_ready

        issue_edit_default_insert_field_form: (function IssueEditor__issue_edit_default_insert_field_form ($link, $placeholder, data) {
            var $form = $(data);
            $link.remove();
            $placeholder.replaceWith($form);
            IssueEditor.focus_form($form, 50);
            return $form;
        }), // issue_edit_default_insert_field_form

        issue_edit_title_insert_field_form: (function IssueEditor__issue_edit_title_insert_field_form ($link, $placeholder, data) {
            var left = $placeholder.position().left, $form;
            $placeholder.parent().after($placeholder);
            $form = IssueEditor.issue_edit_default_insert_field_form($link, $placeholder, data);
            $form.css('left', left + 'px');
            return $form;
        }), // issue_edit_title_insert_field_form

        load_select2: (function IssueEditor__load_select2 (callback) {
            if (typeof $().select2 == 'undefined') {
                var count_done = 0,
                    on_one_done = function() {
                        count_done++;
                        if (count_done == 2) {
                            callback();
                        }
                    };
                $.ajax({
                    url: select2_statics.css,
                    dataType: 'text',
                    cache: true,
                    success: function(data) {
                        $('<style>').attr('type', 'text/css').text(data).appendTo('head');
                        on_one_done();
                    }
                });
                $.ajax({
                    url: select2_statics.js,
                    dataType: 'script',
                    cache: true,
                    success: on_one_done
                });
            } else {
                callback();
            }
        }), // load_select2

        select2_matcher: (function IssueEditor__select2_matcher (term, text) {
                var last = -1;
                term = term.toLowerCase();
                text = text.toLowerCase();
                for (var i = 0; i < term.length; i++) {
                    last = text.indexOf(term[i], last+1);
                    if (last == -1) { return false; }
                }
                return true;
        }), // select2_matcher

        select2_auto_open: (function IssueEditor__select2_auto_open ($select) {
            // http://stackoverflow.com/a/22210140
            $select.one('select2-focus', IssueEditor.on_select2_focus)
                   .on("select2-blur", function () {
                        $(this).one('select2-focus', IssueEditor.on_select2_focus)
                    });
        }), // select2_auto_open

        on_select2_focus: (function IssueEditor__on_select2_focus () {
           var select2 = $(this).data('select2');
            setTimeout(function() {
                if (!select2.opened()) {
                    select2.open();
                }
            }, 0);
        }), // on_select2_focus

        issue_edit_milestone_field_prepare: (function IssueEditor__issue_edit_milestone_field_prepare ($form, dont_load_select2) {
            var $select = $form.find('#id_milestone');
            if (!$select.length) { return; }
            var callback = function() {
                var milestones_data = $select.data('milestones'),
                    format = function(state, include_title) {
                        if (state.children) {
                            return state.text.charAt(0).toUpperCase() + state.text.substring(1) + ' milestones';
                        }
                        var data = milestones_data[state.id];
                        if (data) {
                            var result = '<i class="fa fa-tasks text-' + data.state + '"> </i> <strong>' + (data.title.length > 25 ? data.title.substring(0, 20) + '…' : data.title);
                            if (include_title) {
                                var title = data.state.charAt(0).toUpperCase() + data.state.substring(1) + ' milestone';
                                if (data.state == 'open' && data.due_on) {
                                    title += ', due on ' + data.due_on;
                                }
                                result = '<div title="' + title + '">' + result + '</div>';
                            }
                            return result;
                        } else {
                            return '<i class="fa fa-tasks"> </i> No milestone';
                        }
                    };
                $select.select2({
                    formatSelection: function(state) { return format(state, false); },
                    formatResult:  function(state) { return format(state, true); },
                    escapeMarkup: function(m) { return m; },
                    dropdownCssClass: 'select2-milestone',
                    matcher: IssueEditor.select2_matcher
                });
                IssueEditor.select2_auto_open($select);
                $form.closest('.modal').removeAttr('tabindex');  // tabindex set to -1 bugs select2
            }
            if (dont_load_select2) {
                callback();
            } else {
                IssueEditor.load_select2(callback);
            }
        }), // issue_edit_milestone_field_prepare

        issue_edit_assignee_field_prepare: (function IssueEditor__issue_edit_assignee_field_prepare ($form, dont_load_select2) {
            var $select = $form.find('#id_assignee');
            if (!$select.length) { return; }
            var callback = function() {
                var collaborators_data = $select.data('collaborators'),
                    format = function(state, include_icon) {
                        var data = collaborators_data[state.id];
                        if (data) {
                            var avatar_url = data.avatar_url || default_avatar;
                            result = '<img class="avatar-tiny img-circle" src="' + avatar_url + '" /> <strong>' + (data.username.length > 25 ? data.username.substring(0, 20) + '…' : data.username);
                        } else {
                            result = 'No one assigned';
                        }
                        if (include_icon) {
                            result = '<i class="fa fa-hand-o-right"> </i> ' + result;
                        }
                        return result;
                    };
                $select.select2({
                    formatSelection: function(state) { return format(state, true); },
                    formatResult:  function(state) { return format(state, false); },
                    escapeMarkup: function(m) { return m; },
                    dropdownCssClass: 'select2-assignee',
                    matcher: IssueEditor.select2_matcher
                });
                IssueEditor.select2_auto_open($select);
                $form.closest('.modal').removeAttr('tabindex');  // tabindex set to -1 bugs select2
            }
            if (dont_load_select2) {
                callback();
            } else {
                IssueEditor.load_select2(callback);
            }
        }), // issue_edit_assignee_field_prepare

        issue_edit_labels_field_prepare: (function IssueEditor__issue_edit_labels_field_prepare ($form, dont_load_select2) {
            var $select = $form.find('#id_labels');
            if (!$select.length) { return; }
            var callback = function() {
                var labels_data = $select.data('labels'),
                    format = function(state, include_type) {
                        if (state.children) {
                            return state.text;
                        }
                        var data = labels_data[state.id];
                        var result = data.typed_name;
                        if (include_type && data.type) {
                            result = '<strong>' + data.type + ':</strong> ' + result;
                        }
                        return '<span style="border-bottom-color: #' + data.color + '">' + result + '</span>';
                    },
                    matcher = function(term, text, opt) {
                        return IssueEditor.select2_matcher(term, labels_data[opt.val()].search);
                    };
                $select.select2({
                    formatSelection: function(state) { return format(state, true); },
                    formatResult:  function(state) { return format(state, false); },
                    escapeMarkup: function(m) { return m; },
                    dropdownCssClass: 'select2-labels',
                    matcher: matcher,
                    closeOnSelect: false
                });
                IssueEditor.select2_auto_open($select);
                $form.closest('.modal').removeAttr('tabindex');  // tabindex set to -1 bugs select2
            }
            if (dont_load_select2) {
                callback();
            } else {
                IssueEditor.load_select2(callback);
            }
        }), // issue_edit_labels_field_prepare

        on_issue_edit_field_cancel_click: (function IssueEditor__on_issue_edit_field_cancel_click (ev) {
            var $btn = $(this),
                $form = $btn.closest('form');
            if ($form.data('disabled')) { return false; }
            IssueEditor.disable_form($form);
            $btn.addClass('loading');
            var $container = $form.closest('.issue-container'),
                issue_ident = IssueDetail.get_issue_ident($container),
                is_popup = IssueDetail.is_modal($container);
            IssuesListIssue.open_issue(issue_ident, is_popup, true, true);
            if (is_popup) {
                $container.closest('.modal').attr('tabindex', '-1');
            }
            return false;
        }), // on_issue_edit_field_cancel_click

        on_issue_edit_field_submit: (function IssueEditor__on_issue_edit_field_submit (ev) {
            var $form = $(this);
            if ($form.data('disabled')) { return false; }
            var $btn = $form.find('.btn-save');
            IssueEditor.disable_form($form);
            $btn.addClass('loading');
            $.ajax({
                url: $form.attr('action'),
                data: $form.serialize(),
                type: 'POST',
                success: IssueEditor.on_issue_edit_submit_done,
                error: IssueEditor.on_issue_edit_submit_fail,
                context: IssueEditor.get_form_context($form)
            });
            return false;
        }), // on_issue_edit_field_submit

        on_issue_edit_submit_done: (function IssueEditor__on_issue_edit_submit_done (data) {
            this.$form.find('button.loading').removeClass('loading');
            if (data.trim()) {
                IssueEditor.display_issue(data, this);
            } else {
                IssueEditor.enable_form(this.$form);
                this.$form.find('button.loading').removeClass('loading');
                IssueEditor.focus_form(this.$form);
            }
        }), // on_issue_edit_submit_done

        on_issue_edit_submit_fail: (function IssueEditor__on_issue_edit_submit_fail () {
            IssueEditor.enable_form(this.$form);
            this.$form.find('button.loading').removeClass('loading');
            alert('A problem prevented us to do your action !');
        }), // on_issue_edit_submit_fail

        create: {
            allowed_path_re: new RegExp('^/([\\w\\-\\.]+/[\\w\\-\\.]+)/(?:issues/|dashboard/$)'),
            $modal: null,
            $modal_body: null,
            $modal_footer: null,
            $modal_submit: null,
            $modal_repository_placeholder: null,
            modal_issue_body: '<div class="modal-body"><div class="issue-container"></div></div>',
            get_form: function() {
                return $('#issue-create-form');
            },

            start: (function IssueEditor_create__start () {
                if (!location.pathname.match(IssueEditor.create.allowed_path_re)) {
                    return;
                }
                if ($('#milestone-edit-form:visible').length) {
                    return;
                }
                if ($('#milestone-edit-form:visible').length) {
                    return;
                }
                if (IssueEditor.create.$modal.is(':visible')) {
                    return;
                }
                IssueEditor.create.$modal_repository_placeholder.text(main_repository);
                IssueEditor.create.$modal_footer.hide();
                IssueEditor.create.$modal_body.html('<p class="empty-area"><i class="fa fa-spinner fa-spin"> </i></p>');
                IssueEditor.create.$modal_submit.removeClass('loading');
                IssueEditor.create.$modal.modal('show');
                $.get(create_issue_url)
                    .done(IssueEditor.create.on_load_done)
                    .fail(IssueEditor.create.on_load_failed);
                IssueEditor.create.$modal_footer.find('.alert').remove();
                return false;
            }), // start

            on_load_done: (function IssueEditor_create__on_load_done (data) {
                IssueEditor.create.$modal_body.html(data);
                var $form = IssueEditor.create.get_form();
                IssueEditor.create.update_form($form);
                IssueEditor.focus_form($form, 250);
                IssueEditor.create.$modal_footer.show();
            }), // on_load_done

            on_load_failed: (function($link) {
                IssueEditor.create.$modal_body.html('<div class="alert alert-error">A problem prevented us to display the form</div>');
            }), // on_load_failed

            update_form: (function IssueEditor_create__update_form ($form) {
                var select2_callback = function() {
                    IssueEditor.issue_edit_milestone_field_prepare($form, true);
                    IssueEditor.issue_edit_assignee_field_prepare($form, true);
                    IssueEditor.issue_edit_labels_field_prepare($form, true);
                };
                IssueEditor.load_select2(select2_callback);
            }), // update_form

            on_form_submit: (function IssueEditor_create__on_form_submit (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                var $form = IssueEditor.create.get_form();
                if ($form.data('disabled')) { return false; }
                IssueEditor.disable_form($form);
                IssueEditor.create.$modal_submit.addClass('loading');
                IssueEditor.create.$modal_footer.find('.alert').remove();
                $.post($form.attr('action'), $form.serialize())
                    .done(IssueEditor.create.on_submit_done)
                    .fail(IssueEditor.create.on_submit_failed);
            }), // on_form_submit

            on_submit_done: (function IssueEditor_create__on_submit_done (data) {
                IssueEditor.create.$modal_body.scrollTop(0);
                if (data.substr(0, 6) == '<form ') {
                    // we have an error, the whole form is returned
                    IssueEditor.create.get_form().replaceWith(data);
                    var $form = IssueEditor.create.get_form();
                    IssueEditor.enable_form($form);
                    IssueEditor.focus_form($form, 250);
                    IssueEditor.create.update_form($form);
                    IssueEditor.create.$modal_submit.removeClass('loading');
                } else {
                    // no error, we display the issue
                    IssueEditor.create.display_created_issue(data);
                }
            }), // on_submit_done

            on_submit_failed: (function IssueEditor_create__on_submit_failed () {
                var $form = IssueEditor.create.get_form();
                IssueEditor.enable_form($form);
                IssueEditor.focus_form($form, 250);
                IssueEditor.create.$modal_submit.removeClass('loading');
                IssueEditor.create.$modal_footer.prepend('<div class="alert alert-error">A problem prevented us to save the issue</div>');
            }), // on_submit_failed

            display_created_issue: (function IssueEditor_create__display_created_issue (html) {
                var $html = $('<div/>').html(html),
                    $article = $html.children('article:first-of-type'),
                    number = $article.data('number'),
                    context = {
                        issue_ident: {
                            repository: $article.data('repository'),
                            number: number || 'pk-' + $article.data('issue-id')
                        }
                    },
                    container = IssueDetail.get_container_waiting_for_issue(context.issue_ident, true, true);
                IssueEditor.create.$modal.modal('hide');
                context.$node = container.$node;
                IssueEditor.display_issue($html.children(), context);
            }), // display_created_issue

            on_created_modal_hidden: (function IssueEditor_create__on_created_modal_hidden () {
                var $modal = $(this);
                setTimeout(function() { $modal.remove(); }, 50);
            }), // on_created_modal_hidden

            init: (function IssueEditor_create__init () {
                IssueEditor.create.$modal = $('#issue-create-modal');
                IssueEditor.create.$modal_repository_placeholder = IssueEditor.create.$modal.find('.modal-header > h6 > span');
                IssueEditor.create.$modal_footer = IssueEditor.create.$modal.children('.modal-footer');
                IssueEditor.create.$modal_body = IssueEditor.create.$modal.children('.modal-body');
                IssueEditor.create.$modal_submit = IssueEditor.create.$modal_footer.find('button.submit');

                jwerty.key('c', Ev.key_decorate(IssueEditor.create.start));
                $('.add-issue-btn a').on('click', Ev.stop_event_decorate(IssueEditor.create.start));
                $document.on('submit', '#issue-create-form', IssueEditor.create.on_form_submit);
                $document.on('click', '#issue-create-modal .modal-footer button.submit', IssueEditor.create.on_form_submit);
                $document.on('hidden.modal', '#modal-issue-created', IssueEditor.create.on_created_modal_hidden);
            }), // IssueEditor_create__init
        },

        init: (function IssueEditor__init () {
            $document.on('submit', '.issue-edit-state-form', IssueEditor.on_state_submit);

            $document.on('click', 'a.issue-edit-btn', Ev.stop_event_decorate(IssueEditor.on_issue_edit_field_click));
            $document.on('click', 'form.issue-edit-field button.btn-cancel', Ev.stop_event_decorate(IssueEditor.on_issue_edit_field_cancel_click));
            $document.on('submit', 'form.issue-edit-field', Ev.stop_event_decorate(IssueEditor.on_issue_edit_field_submit));

            $document.on('click', '.comment-create-placeholder button', IssueEditor.on_comment_create_placeholder_click);

            $document.on('submit', '.comment-form', IssueEditor.on_comment_submit);
            $document.on('focus', '.comment-form textarea', IssueEditor.on_comment_textarea_focus);

            $document.on('click', '.comment-create-form button[type=button]', IssueEditor.on_comment_create_cancel_click);
            $document.on('click', '.comment-edit-form button[type=button], .comment-delete-form button[type=button]', IssueEditor.on_comment_edit_or_delete_cancel_click);

            $document.on('click', '.comment-edit-btn', Ev.stop_event_decorate(IssueEditor.on_comment_edit_click));
            $document.on('click', '.comment-delete-btn', Ev.stop_event_decorate(IssueEditor.on_comment_delete_click));

            $document.on('click', 'td.code span.btn-comment', IssueEditor.on_new_entry_point_click);

            IssueEditor.create.init();
        }) // init
    }; // IssueEditor
    IssueEditor.init();

    // focus input for repos-switcher
    var $repos_switcher_input = $('#repository-switcher-filter').find('input');
    if ($repos_switcher_input.length) {
        $repos_switcher_input.closest('li').on('click', function(ev) { ev.stopPropagation(); })
        $('#repository-switcher').on('focus', Ev.set_focus($repos_switcher_input, 200))
            .on('focus', function() {
                var $link = $(this);
                $link.next().css('max-height', $(window).height() - $link.offset().top - $link.outerHeight() - 10);
            });
    }
    // auto-hide owner if it has no repo found on quicksearch
    var $repos_switcher_groups = $('#repository-switcher-content li.subscriptions-group');
    $repos_switcher_input.on('quicksearch.after', function() {
        $repos_switcher_groups.each(function() {
            var $group = $(this);
            $group.toggle(!!$group.find('li:not(.hidden)').length);
        });
    });

    var Activity = {
        selectors: {
            main: '.activity-feed',
            issue_link: '.box-section > h3 > a, a.referenced_issue',
            buttons: {
                refresh: '.timeline-refresh',
                more: '.placeholder.more a'
            },
            entries: {
                all: '.chat-box > li',
                first: '.chat-box:first > li:first',
                last: '.chat-box:last > li:last'
            },
            containers: {
                issues: '.box-section',
                repositories: '.activity-repository'
            },
            count_silent: {
                issues: '.box-section.silent',
                repositories: '.activity-repository.silent .box-section'
            },
            find_empty: ':not(:has(.chat-box > li))',
            filter_checkboxes: '.activity-filter input',
            filter_links: '.activity-filter a'
        },

        on_issue_link_click: (function Activity__on_issue_link_click () {
            var $link = $(this),
                $block = $link.data('number') ? $link : $link.closest('.box-section'),
                issue = new IssuesListIssue({}, null);
            issue.set_issue_ident({
                number: $block.data('number'),
                repository: $block.data('repository')
            });
            issue.get_html_and_display($link.attr('href'), true);
            return false;
        }), // on_issue_link_click

        get_main_node: (function Activity__get_main_node ($node) {
            return $node.closest(Activity.selectors.main);
        }), // get_main_node

        get_existing_entries_for_score: (function Activity__get_existing_entries_for_score($pivot, where, score) {
            var result = [], $check = $pivot, $same_score_entries;
            if (!score) { return };
            while (true) {
                $check = $check[where]();
                if (!$check.length) { break; }
                $same_score_entries = $check.find(Activity.selectors.entries.all + '[data-score="' + score + '"]');
                if (!$same_score_entries.length) { break; }
                result = result.concat($same_score_entries.map(function() {return $(this).data('ident'); }).toArray());
            }
            return result;
        }), // get_existing_entries_for_score

        add_loaded_entries: (function Activity__add_loaded_entries($main_node, data, limits, $placeholder, silent, callback) {
            var $container = $('<div />'),
                mode = $main_node.data('mode'),
                idents = {}, $check, $same_score_entries,
                $entries, $entry, is_min, is_max, count = 0;

            // put data in a temporary container to manage them
            $container.append(data);
            $entries = $container.find(Activity.selectors.entries.all);

            // get idents for existing entries with same min/max scores
            if (limits.min) {
                idents.min = Activity.get_existing_entries_for_score($placeholder, 'next', limits.min);
            }
            if (limits.max) {
                idents.max = Activity.get_existing_entries_for_score($placeholder, 'prev', limits.max);
            }

            // we need numbers to compare
            if (limits.min) { limits.min = parseFloat(limits.min, 10)};
            if (limits.max) { limits.max = parseFloat(limits.max, 10)};

            // remove entries with boundaries already presents
            for (var i = 0; i < $entries.length; i++) {
                $entry = $($entries[i]);
                score = $entry.data('score');
                is_min = (limits.min && score == limits.min);
                is_max = (limits.max && score == limits.max);
                if (is_min || is_max) {
                    ident = $entry.data('ident');
                    if (    is_min && idents.min && $.inArray(ident, idents.min) != -1
                         ||
                            is_max && idents.max && $.inArray(ident, idents.max) != -1
                        ) {
                        $entry.remove();
                    }
                }
            }

            // clean empty nodes
            if (mode == 'issues' || mode == 'repositories') {
                $container.find(Activity.selectors.containers.issues + Activity.selectors.find_empty).remove();
                if (mode == 'repositories') {
                    $container.find(Activity.selectors.containers.repositories + Activity.selectors.find_empty).remove();
                }
            }

            count = $container.find(Activity.selectors.entries.all).length;

            if (!silent) {
                // remove old "recent" marks
                $main_node.find(Activity.selectors.containers[mode] + '.recent:not(.silent)').removeClass('recent');
            }

            // insert data if there is still
            if (count) {
                $entries = $container.children();
                if (silent) {
                    $entries.addClass('silent');
                    $entries.insertAfter($placeholder);
                } else {
                    $entries.replaceAll($placeholder);
                    setTimeout(function() { $entries.addClass('recent'); }, 10);
                }
                if (callback) { callback('ok'); }
            } else {
                if (!silent) {
                    Activity.update_placeholder($placeholder, 'nothing', callback);
                } else {
                    if (callback) { callback('nothing'); }
                }
            }

            Activity.toggle_empty_parts($main_node);

            return count;
        }), // add_loaded_entries

        placeholders: {
            nothing: {
                message: 'Nothing new',
                icon: 'fa fa-eye-slash',
                delay: 1000
            },
            error: {
                message: 'Error while loading',
                icon: 'fa fa-times-circle',
                delay: 3000
            },
            loading: {
                message: 'Loading',
                icon: 'fa fa-spinner fa-spin',
                delay: -1
            },
            more: {
                message: 'Load more',
                icon: 'fa fa-plus',
                delay: -1,
                classes: 'box-footer',
                link: '#'
            },
            missing: {
                message: 'Load missing',
                icon: 'fa fa-plus',
                delay: -1,
                classes: 'more box-footer',
                link: '#'
            },
            new_activity: {
                message: '<span>New activity</span> available, click to see them!',
                icon: 'fa fa-refresh',
                delay: -1,
                classes: 'timeline-refresh',
                link: '#'
            }
        }, // placeholders

        update_placeholder: (function Activity__update_placeholder($placeholder, type, callback, replace_type) {
            var params = Activity.placeholders[type];
            var html = '<i class="' + params.icon + '"> </i> ' + params.message;
            if (params.link) {
                html = '<a href="' + params.link + '">' + html + '</a>';
            }
            $placeholder.html(html);
            $placeholder[0].className = 'placeholder visible ' + type + (params.classes ? ' ' + params.classes : '');  // use className to remove all previous
            if (params.delay != -1) {
                setTimeout(function() {
                    if (replace_type) {
                        Activity.update_placeholder($placeholder, replace_type);
                        if (callback) { callback(type); }
                    } else {
                        $placeholder.removeClass('visible');
                        setTimeout(function() {
                            $placeholder.remove();
                            if (callback) { callback(type); }
                        }, 320);
                    }
                }, params.delay);
            }
        }), // update_placeholder

        load_data: (function Activity__load_data($main_node, limits, $placeholder, silent, callback, retry_placeholder) {
            var data = { partial: 1};

            if (limits.min) { data.min = limits.min; }
            if (limits.max) { data.max = limits.max; }

            $.ajax({
                url: $main_node.data('url'),
                data: data,
                dataType: 'html',
                success: function(data) {
                    Activity.add_loaded_entries($main_node, data, limits, $placeholder, silent, callback);
                },
                error: function() {
                    if (silent) {
                        callback('error');
                    } else {
                        Activity.update_placeholder($placeholder, 'error', callback, retry_placeholder);
                    }
                }
            });

        }), // load_data

        on_refresh_button_click: (function Activity__on_refresh_button_click () {
            var $main_node, $refresh_buttons, mode, $placeholder, $first_entry, score, $silent_entries;

            $main_node = Activity.get_main_node($(this));

            $refresh_buttons = $main_node.find('.timeline-refresh');

            if ($refresh_buttons.hasClass('disabled')) { return false; }
            $refresh_buttons.addClass('disabled');

            $main_node.children('.box-content').scrollTop(1).scrollTop(0);
            mode = $main_node.data('mode');

            $silent_entries = $main_node.find(Activity.selectors.containers[mode] + '.silent');

            if ($silent_entries.length) {

                $main_node.find('.placeholder.new_activity').remove();
                $main_node.find(Activity.selectors.containers[mode] + '.recent:not(.silent)').removeClass('recent');
                $silent_entries.removeClass('silent').addClass('recent');
                $refresh_buttons.removeClass('disabled');

            } else {

                $placeholder = $('<div class="placeholder loading"><i class="' + Activity.placeholders.loading.icon + '"> </i> ' + Activity.placeholders.loading.message + '</div>');
                $main_node.find(Activity.selectors.containers[mode]).first().before($placeholder);
                setTimeout(function() { $placeholder.addClass('visible'); }, 10);

                Activity.get_fresh_data($main_node, $placeholder, false, function(result_type) {
                    $refresh_buttons.removeClass('disabled');
                });
            }

            return false;
        }), // on_refresh_button_click

        display_silent_activity: (function Activity__display_silent_activity() {

        }), // display_silent_activity

        get_fresh_data: (function Activity__get_fresh_data($main_node, $placeholder, silent, callback) {
            var score = $main_node.find(Activity.selectors.entries.first).data('score');
            Activity.load_data($main_node, {min: score}, $placeholder, silent, callback);
        }), // get_fresh_data

        check_new_activity: (function Activity__check_new_activity($main_node) {
            var $placeholder = $('<div class="placeholder silent-checking"></div>'),
                $new_activity_placeholder = $main_node.find('.placeholder.new_activity'),
                mode = $main_node.data('mode');

            $main_node.find(Activity.selectors.containers[mode]).first().before($placeholder);

            Activity.get_fresh_data($main_node, $placeholder, true, function(result_type) {
                if (result_type == 'ok') {
                    if ($new_activity_placeholder.length) {
                        $placeholder.remove();
                    } else {
                        Activity.update_placeholder($placeholder, 'new_activity');
                        $new_activity_placeholder = $placeholder;
                    }
                    var count =  $silent_entries = $main_node.find(Activity.selectors.count_silent[mode]).length;
                    $new_activity_placeholder.find('span').text(count + ' new entr' + (count > 1 ? 'ies' : 'y'));
                    $new_activity_placeholder.addClass('flash');
                    setTimeout(function() {
                        $new_activity_placeholder.removeClass('flash');
                    }, 1000);
                } else {
                    $placeholder.remove();
                }
            });

        }), // check_new_activity

        delay_check_new_activity: (function Activity__delay_check_new_activity($main_node) {
            if (typeof $main_node.selector == 'undefined') {
                // node is passed as a string when html loaded for the first time
                $main_node = $($main_node);
                if (!$main_node.length) {
                    setTimeout(function() {
                        Activity.delay_check_new_activity($main_node.selector);
                    }, 1000);
                    return;
                }
            }
            setInterval(function() {
                Activity.check_new_activity($main_node);
            }, 30000);
        }), // delay_check_new_activity

        on_more_button_click: (function Activity__on_more_button_click () {
            var $this = $(this), $main_node,
                $placeholder = $this.parent(),
                $previous_entry, $next_entry,
                previous_score, next_score,
                limits = {}
                is_missing_btn = $placeholder.hasClass('missing');

            if ($this.hasClass('disabled')) { return false; }
            $this.addClass('disabled');

            Activity.update_placeholder($placeholder, 'loading');

            $main_node = Activity.get_main_node($placeholder);

            $previous_entry = $placeholder.prev().find(Activity.selectors.entries.last);
            if ($previous_entry.length) {
                limits.max = $previous_entry.data('score');
            }
            $next_entry = $placeholder.next().find(Activity.selectors.entries.first);
            if ($next_entry.length) {
                limits.min = $next_entry.data('score');
            }

            Activity.load_data($main_node, limits, $placeholder, false, null, is_missing_btn ? 'missing' : 'more');

            return false;
        }), // on_more_button_click

        on_filter_change: (function Activity__on_filter_change (ev) {
            var $checkbox = $(this).closest('a').find('input'),  // works if ev on A or INPUT
                checked = $checkbox.is(':checked'),
                is_all = $checkbox.attr('name') == 'toggle-all',
                $feed = $checkbox.closest('.activity-feed'),
                $checkboxes = null;
            if (is_all) {
                $checkboxes = $feed.find(Activity.selectors.filter_checkboxes + ':not([name=toggle-all])');
            } else {
                $checkboxes = $checkbox;
            }
            $checkboxes.each(function() {
                var $checkbox = $(this),
                    klass = 'hide-' + $checkbox.attr('name');
                if (is_all) { $checkbox.prop('checked', checked); }
                $feed.toggleClass(klass, !checked);
            });
            Activity.toggle_empty_parts($feed);
            return false;
        }), // on_filter_change

        on_filter_link_click: (function Activity__on_filter_link_click (ev) {
            // avoid propagation to boostrap dropdown which would close the dropdown
            ev.stopPropagation();
        }), // on_filter_link_click

        toggle_empty_parts: (function Activity__toggle_empty_parts ($feed) {
            var checked_filters = [],
                $inputs = $feed.find('.activity-filter input:checked');
            for (var i = 0; i < $inputs.length; i++) {
                checked_filters.push('.' + $inputs[i].name);
            };
            var filter = checked_filters.join(', '),
                no_filter = checked_filters.length == 0,
                $sections = $feed.find('.box-section');
            for (var j = 0; j < $sections.length; j++) {
                var $section = $($sections[j]);
                $section.toggleClass('hidden', no_filter || $section.children('ul').children(filter).length == 0);
            };
            if ($feed.hasClass('for-repositories')) {
                var $repositories = $feed.find('.activity-repository');
                for (var k = 0; k < $repositories.length; k++) {
                    var $repository = $($repositories[k]);
                    $repository.toggleClass('hidden', no_filter || $repository.children('.box-content').children(':not(.hidden)').length == 0);
                };
            }
        }), // toggle_empty_parts

        init_feeds: (function Activity__init_feeds () {
            setInterval(function() {
                var $feeds = $(Activity.selectors.main);
                for (var i = 0; i < $feeds.length; i++) {
                    replace_time_ago($feeds[i]);
                }
            }, 60000);

            var $feeds = $(Activity.selectors.main);
            for (var j = 0; j < $feeds.length; j++) {
                Activity.toggle_empty_parts($($feeds[j]));
            }
        }), // init_feeds

        init_events: (function Activity__init_events () {
            $document.on('click', Activity.selectors.main + ' ' + Activity.selectors.issue_link, Ev.stop_event_decorate(Activity.on_issue_link_click));
            $document.on('click', Activity.selectors.main + ' ' + Activity.selectors.buttons.refresh, Ev.stop_event_decorate(Activity.on_refresh_button_click));
            $document.on('click', Activity.selectors.main + ' ' + Activity.selectors.buttons.more, Ev.stop_event_decorate(Activity.on_more_button_click));
            $document.on('click', Activity.selectors.main + ' ' + Activity.selectors.filter_links, Ev.stop_event_decorate(Activity.on_filter_link_click));
            $document.on('change', Activity.selectors.main + ' ' + Activity.selectors.filter_checkboxes, Ev.stop_event_decorate(Activity.on_filter_change));
        }), // init_events

        init: (function Activity__init () {
            Activity.init_feeds();
            Activity.init_events();
        }) // init
    }; // Activity
    Activity.init();
    window.Activity = Activity;

    // if there is a collapse inside another, we don't want fixed heights, so always remove them
    $document.on('shown.collapse', '.collapse', function() {
        $(this).css('height', 'auto');
    });

    // if a link is on a collapse header, deactivate the collapse on click
    $document.on('click', '[data-toggle=collapse] a:not([href=#])', function(ev) {
        ev.stopPropagation();
    });

});

