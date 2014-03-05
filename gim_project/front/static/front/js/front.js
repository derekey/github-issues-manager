$().ready(function() {

    var $document = $(document),
        $body = $('body'),
        main_repository = $body.data('repository');

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

        stop_event_decorate_dropdown: (function stop_event_decorate_dropdown(callback) {
            /* Return a function to use as a callback for clicks on dropdown items
               It will close the dropwdown before calling the callback, and will
               return false to tell to the main decorator to stop the event
            */
            var decorator = function(e) {
                var dropdown = $(e.target).closest('.dropdown');
                if (dropdown.hasClass('open')) {
                    dropdown.children('.dropdown-toggle').dropdown('toggle');
                }
                callback(e);
                return false;
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
            var issue_node = $(e.target).closest(IssuesListIssue.selector);
            if (!issue_node.length || !issue_node[0].IssuesListIssue) { return; }
            return issue_node[0].IssuesListIssue[group_method]();
        };
        return stop ? Ev.stop_event_decorate(decorator) : decorator;
    }); // IssuesListIssue_on_issue_node_event

    IssuesListIssue.init_events = (function IssuesListIssue_init_events () {
        $document.on('click', IssuesListIssue.selector + ' ' + IssuesListIssue.link_selector, IssuesListIssue.on_issue_node_event('on_click', true));
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
        if (!no_loading) { IssueDetail.set_container_loading(container); }
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
            issue.get_html_and_display(url, force_popup);
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
        init_users: function(user_type, user_class, filter_name) {
            if (typeof IssuesFiltersUsers === 'undefined' || typeof IssuesFiltersUsers[user_type] === 'undefined' ) { return; }
            var all_html = [], i, username, url;
            for (i = 0; i < IssuesFiltersUsers[user_type].list.length; i++) {
                username = IssuesFiltersUsers[user_type].list[i];
                url = IssuesFiltersUsers[user_type].url.replace('%(username)s', username);
                all_html.push('<li class="' + user_class + '"><a href="' + url + '">' + username + '</a></li>');
            }
            delete IssuesFiltersUsers[user_type];
            document.getElementById('filter-' + filter_name).insertAdjacentHTML('beforeend', all_html.join(''));
        },
        init: function() {
            IssuesFilters.init_users('creators', 'creator', 'created_by');
            IssuesFilters.init_users('closers', 'closer', 'closed_by');
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

    var toggle_full_screen_for_current_modal = (function toggle_full_screen_for_current_modal() {
        var $modal = $('.modal.in');
        if ($modal.length) {
            $modal.toggleClass('full-screen');
        }
        return false; // stop event propagation
    }); // toggle_full_screen_for_current_modal

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
            return '/' + issue_ident.repository + '/issues/' + issue_ident.number;
        }), // get_url_for_ident

        on_issue_loaded: (function IssueDetail__on_issue_loaded ($node) {
            var is_modal = IssueDetail.is_modal($node);
            if (is_modal) {
                // focusing $node doesn't FUCKING work
                $node.find('header h3 a').focus();
            }
            // set waypoints
            IssueDetail.set_issue_waypoints($node, is_modal);
        }), // on_issue_loaded

        get_scroll_context: (function IssueDetail__get_scroll_context ($node, is_modal) {
            if (typeof is_modal === 'undefined') {
                is_modal = IssueDetail.is_modal($node);
            }
            return is_modal ? $node.parent() : $node;
        }), // get_scroll_context

        set_issue_waypoints: (function IssueDetail__set_issue_waypoints ($node, is_modal) {
            var issue_ident = IssueDetail.get_issue_ident($node);
            setTimeout(function() {
                if (!IssueDetail.is_issue_ident_for_node($node, issue_ident)) { return; }
                var $context = IssueDetail.get_scroll_context($node, is_modal);
                $node.find(' > article > .area-top header').waypoint('sticky', {
                    context: $context,
                    stuckClass: 'area-top stuck'
                });
                var $tabs = $node.find('.pr-tabs');
                if ($tabs.length) {
                    $tabs.waypoint('sticky', {
                        context: $context,
                        stuckClass: 'area-top stuck',
                        offset: 47  // stuck header height
                    })
                }
            }, 500);
        }), // set_issue_waypoints

        set_tab_files_issue_waypoints: (function IssueDetail__set_tab_files_issue_waypoints ($node, $context) {
            var $files_list_container = $node.find('.pr-files-list-container');
            if ($files_list_container.length) {
                if (!$context) {
                    $context = IssueDetail.get_scroll_context($node);
                }
                $files_list_container.waypoint('sticky', {
                    context: $context,
                    wrapper: '<div class="sticky-wrapper files-list-sticky-wrapper" />',
                      offset: 84  // 47 for stuck header height + 37 for stuck tabs height
                });
            }
        }), // set_tab_files_issue_waypoints

        unset_issue_waypoints: (function IssueDetail__unset_issue_waypoints ($node) {
            $node.find(' > article > .area-top header').waypoint('unsticky');
            $node.find('.pr-tabs').waypoint('unsticky');
            $node.find('.pr-files-list-container').waypoint('unsticky');
        }), // unset_issue_waypoints

        is_modal: (function IssueDetail__is_modal ($node) {
            return !!$node.data('$modal');
        }), // is_modal

        enhance_modal: (function IssueDetail__enhance_modal ($node) {
            $node.find('.issue-nav').append('<button type="button" class="close" data-dismiss="modal" title="Close" aria-hidden="true">&times;</button>');
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
            IssueDetail.on_issue_loaded(container.$node);
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
            IssueDetail.fill_container(container, '<p class="empty-area"><i class="icon-spinner icon-spin"> </i></p>');
        }), // set_container_loading

        select_tab: (function IssueDetail__select_tab (panel, type) {
            var $tab_link = panel.$node.find('.pr-' + type + '-tab > a');
            if ($tab_link.length) { $tab_link.focus().click(); }
            return false;
        }), // select_tab
        select_discussion_tab: function(panel) { return IssueDetail.select_tab(panel, 'discussion'); },
        select_commits_tab: function(panel) { return IssueDetail.select_tab(panel, 'commits'); },
        select_files_tab: function(panel) { return IssueDetail.select_tab(panel, 'files'); },

        on_files_list_loaded: (function IssueDetail__on_files_list_loaded ($node, $target) {
            if ($target.data('files-list-loaded')) { return;}
            $target.data('files-list-loaded', true);
            IssueDetail.set_tab_files_issue_waypoints($node);
            $target.find('.pr-files-list a.path').first().click();
        }), // on_files_list_loaded

        on_files_list_click: (function IssueDetail__on_files_list_click (ev) {
            var $link = $(this),
                $target = $($link.attr('href')),
                $node = $link.closest('.issue-container');
            IssueDetail.scroll_in_files_list($node, $target);
            IssueDetail.set_active_file($node, $link.closest('tr').data('pos'), true);
            if (!ev.no_file_focus) {
                $target.find('.box-header a.path').focus();
            }
            return false;
        }), // on_files_list_click

        scroll_in_files_list: (function IssueDetail__scroll_in_files_list ($node, $target, delta) {
            var is_modal = IssueDetail.is_modal($node),
                $context = IssueDetail.get_scroll_context($node, is_modal),
                is_list_on_top = !parseInt($node.find('.pr-files-list-container').css('border-right-width'), 10),
                // is_full_screen = ($node.hasClass('big-issue')),
                stuck_height = $node.find('.sticky-wrapper' + (is_list_on_top ? '' : ':not(.files-list-sticky-wrapper)'))
                               .toArray()
                               .reduce(function(height, wrapper) {
                                    var $wrapper = $(wrapper),
                                        $stickable = $wrapper.children().first();
                                    return height + ($stickable.hasClass('stuck') ? $stickable : $wrapper).outerHeight();
                                }, 0),
                position = (is_modal ? $target.position().top : $target.offset().top)
                         + (is_modal ? 0 : $context.scrollTop())
                          - stuck_height
                          + (is_modal ? (is_list_on_top ? 5 : 303) : -52) // manual finding... :(
                          - 15 // adjust (margin ?)
                          - (delta || 0);

            $context.scrollTop(position);
        }), // scroll_in_files_list

        on_files_list_toggle: (function IssueDetail__on_files_list_toggle (ev) {
            var $files_list = $(this),
                $container = $files_list.closest('.pr-files-list-container');
            if ($container.hasClass('stuck')) {
                $container.parent().height($container.outerHeight());
            }
            if ($files_list.hasClass('in')) {
               IssueDetail.set_active_file_visible($files_list);
            }
        }), // on_files_list_toggle

        toggle_files_list: (function IssueDetail__toggle_files_list () {
            var $node = $(this).closest('.issue-container'),
                $link = $node.find('.pr-files-list-container .files-list-summary');
            if ($link.length) { $link.click(); }
        }), // toggle_files_list

        on_file_mouseenter: (function IssueDetail__on_file_mouseenter (ev) {
            var $file_node = $(this),
                $node = $file_node.closest('.issue-container');
            IssueDetail.set_active_file($node, $file_node.data('pos'), false);
        }), // on_file_mouseenter

        go_to_previous_file: (function IssueDetail__go_to_previous_file () {
            var $node = $(this).closest('.issue-container'),
                $files_list = $node.find('.pr-files-list'),
                $current_line = $files_list.find('tr.active'),
                $line = $current_line.prevAll('tr:not(.hidden)').first();
            if ($line.length) {
                $line.find('a').click();
            }
            return false;
        }), // go_to_previous_file

        go_to_next_file: (function IssueDetail__go_to_next_file () {
            var $node = $(this).closest('.issue-container'),
                $files_list = $node.find('.pr-files-list'),
                $current_line = $files_list.find('tr.active'),
                $line = $current_line.nextAll('tr:not(.hidden)').first();
            if ($line.length) {
                $line.find('a').click();
            }
            return false;
        }), // go_to_next_file

        on_files_filter_done: (function IssueDetail__on_files_filter_done () {
            var $node = $(this).closest('.issue-container');
            if (!$node.find('.pr-files-tab.active').length) { return; }
            var $files_list = $node.find('.pr-files-list'),
                $first_link = $files_list.find('tr:not(.hidden) a').first();
            if (($first_link).length) {
                $first_link.trigger({type: 'click', no_file_focus: true});
            }
        }), // on_files_filter_done

        set_active_file: (function IssueDetail__set_active_file ($node, pos, reset_active_comment) {
            var $files_list = $node.find('.pr-files-list'),
                $line;
            if (!$files_list.length) { return; }
            $line = $files_list.find('tr:nth-child('+ pos +')');
            $files_list.find('tr.active').removeClass('active');
            $line.addClass('active');
            IssueDetail.set_active_file_visible($files_list, $line);
            $node.find('.go-to-previous-file').parent().toggleClass('disabled', $line.prevAll('tr:not(.hidden)').length === 0);
            $node.find('.go-to-next-file').parent().toggleClass('disabled', $line.nextAll('tr:not(.hidden)').length === 0);
            if (reset_active_comment) {
                $files_list.closest('.pr-files-list-container').data('active-comment', null);
                $node.find('.go-to-previous-file-comment, .go-to-next-file-comment').parent().removeClass('disabled');
            }
        }), // set_active_file

        set_active_file_visible: (function IssueDetail__set_active_file_visible ($files_list, $line) {
            var line_top, line_height, list_visible_height, list_scroll;
            if (typeof $files_list == 'undefined') {
                $files_list = $node.find('.pr-files-list');
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
                $files_list.scrollTop(list_scroll + line_top);
                return;
            }
            line_height = $line.height();
            list_visible_height = $files_list.height();
            // in the visible part: do nothing
            if (line_top + line_height < list_visible_height) {
                return;
            }
            // below the visible part: set it visible at the bottom
            $files_list.scrollTop(list_scroll + line_top - list_visible_height + line_height);
        }), // set_active_file_visible

        visible_files_comments: (function IssueDetail__visible_files_comments ($node) {
            var $files_list = $node.find('.pr-files-list');
            if ($files_list.length) {
                return $files_list.find('tr:not(.hidden) a')
                            .toArray()
                            .reduce(function(groups, file_link) {
                                return groups.concat($(
                                    $(file_link).attr('href')
                                ).find('.pr-comments').toArray());
                            }, []);
            } else {
                return [];
            }
        }), // visible_files_comments

        go_to_previous_file_comment: (function IssueDetail__go_to_previous_file_comment () {
            var $node = $(this).closest('.issue-container');
            IssueDetail.go_to_file_comment($node, 'previous');
            return false;
        }), // go_to_previous_file_comment

        go_to_next_file_comment: (function IssueDetail__go_to_next_file_comment () {
            var $node = $(this).closest('.issue-container');
            IssueDetail.go_to_file_comment($node, 'next');
            return false;
        }), // go_to_next_file_comment

        go_to_file_comment: (function IssueDetail__go_to_file_comment ($node, direction) {
            var $files_list_container = $node.find('.pr-files-list-container'),
                $files_list = $node.find('.pr-files-list'),
                comments = IssueDetail.visible_files_comments($node),
                current, comment, $comment, $file_node, position, file_pos;

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
                        if ($(comments[i]).closest('.pr-file').data('pos') >= file_pos) {
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
            $file_node = $comment.closest('.pr-file');
            $files_list_container.data('active-comment', comment);
            IssueDetail.set_active_file($node, $file_node.data('pos'), false);
            IssueDetail.scroll_in_files_list($node, $comment, 30);  // 30 = 2 previous diff lines
            $node.find('.go-to-previous-file-comment').parent().toggleClass('disabled', index === 0);
            $node.find('.go-to-next-file-comment').parent().toggleClass('disabled', index === comments.length - 1);
        }), // go_to_file_comment

        load_tab: (function IssueDetail__load_tab (ev) {
            var $tab = $(ev.target),
                $target = $($tab.attr('href')),
                $node = $tab.closest('.issue-container');
            // load content if not already available
            if ($target.children('.empty-area').length) {
                $.ajax({
                    url: $target.data('url'),
                    success: function(data) {
                        $target.html(data);
                        if ($target.hasClass('issue-files')) {
                            IssueDetail.on_files_list_loaded($node, $target);
                        }
                    },
                    error: function() {
                        $target.children('.empty-area').html('Loading failed :(');
                    }
                });
            } else {
                if ($target.hasClass('issue-files')) {
                    IssueDetail.on_files_list_loaded($node, $target);
                }
            }
            // if the tabs holder is stuck, we'll scroll in a cool way
            var $tabs_holder = $node.find('.pr-tabs'),
                $stuck_header, position, $stuck,
                is_modal = IssueDetail.is_modal($node),
                $context = IssueDetail.get_scroll_context($node, is_modal);
            if ($tabs_holder.hasClass('stuck')) {
                $stuck_header = $node.find(' > article > .area-top header');
                position = $node.find('.tab-content').position().top
                         + (is_modal ? 0 : $context.scrollTop())
                         - $stuck_header.height()
                         - $tabs_holder.height()
                         - 3 // adjust
                $context.scrollTop(position);
            }
        }), // load_tab

        on_current_panel_key_event: (function IssueDetail__on_current_panel_key_event (method) {
            var decorator = function(e) {
                if (PanelsSwpr.current_panel.obj != IssueDetail) { return; }
                return IssueDetail[method](PanelsSwpr.current_panel);
            };
            return Ev.key_decorate(decorator);
        }), // on_current_panel_key_event

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
            PanelsSwpr.select_panel($modal.data('previous-panel'));
            $modal.data('$container').html('');
        }), // on_modal_hidden

        on_files_list_key_event:  (function IssueDetail__on_files_list_key_event (method) {
            var decorator = function(e) {
                if (PanelsSwpr.current_panel.obj != IssueDetail) { return; }
                var $node = PanelsSwpr.current_panel.$node,
                    $tab = $node.find('.pr-files-tab.active');
                if (!$tab.length) { return; }
                return IssueDetail[method].call($tab);
            };
            return Ev.key_decorate(decorator);
        }), // on_files_list_key_event

        focus_search_input: (function IssueDetail__focus_search_input () {
            var $node = $(this).closest('.issue-container'),
                $files_list_container = $node.find('.pr-files-list-container'),
                $search_input = $files_list_container.find('input.quicksearch');
            $search_input.focus();
            return false;
        }), // focus_search_input

        toggle_full_screen: (function IssueDetail__toggle_full_screen (panel) {
            if (IssueDetail.is_modal(panel.$node)) {
                toggle_full_screen_for_current_modal();
            }
            panel.$node.toggleClass('big-issue');
            return false;
        }), // toggle_full_screen

        view_on_github: (function IssueDetail__view_on_github (panel) {
            var $link = panel.$node.find('header h3 a').first();
            window.open($link.attr('href'), '_blank');
            return false;
        }), // view_on_github

        init: (function IssueDetail__init () {
            // init modal container
            IssueDetail.$modal_body = IssueDetail.$modal.children('.modal-body'),
            IssueDetail.$modal_container = IssueDetail.$modal_body.children('.issue-container'),
            IssueDetail.$modal_container.data('$modal', IssueDetail.$modal);
            IssueDetail.$modal.data('$container', IssueDetail.$modal_container);

            // full screen mode
            jwerty.key('s', IssueDetail.on_current_panel_key_event('toggle_full_screen'));
            jwerty.key('s', IssueDetail.on_main_issue_panel_key_event('toggle_full_screen'));
            $document.on('click', '.resize-issue', IssueDetail.on_current_panel_key_event('toggle_full_screen'));

            jwerty.key('v', IssueDetail.on_current_panel_key_event('view_on_github'));
            jwerty.key('v', IssueDetail.on_main_issue_panel_key_event('view_on_github'));

            // tabs activation
            jwerty.key('shift+d', IssueDetail.on_current_panel_key_event('select_discussion_tab'));
            jwerty.key('shift+c', IssueDetail.on_current_panel_key_event('select_commits_tab'));
            jwerty.key('shift+f', IssueDetail.on_current_panel_key_event('select_files_tab'));
            $document.on('shown.tab', '.pr-tabs a', IssueDetail.load_tab);

            // modal events
            if (IssueDetail.$modal.length) {
                IssueDetail.$modal.on('shown.modal', IssueDetail.on_modal_shown);
                IssueDetail.$modal.on('hidden.modal', IssueDetail.on_modal_hidden);
            }

            // waypoints for loaded issue
            if (IssueDetail.$main_container.data('number')) {
                IssueDetail.set_issue_waypoints(IssueDetail.$main_container);
            }

            // files list summary
            $document.on('click', '.pr-files-list a', Ev.stop_event_decorate(IssueDetail.on_files_list_click));
            $document.on('shown.collapse hidden.collapse', '.pr-files-list', IssueDetail.on_files_list_toggle);
            $document.on('mouseenter', '.pr-file', IssueDetail.on_file_mouseenter);
            jwerty.key('f', IssueDetail.on_files_list_key_event('focus_search_input'));
            jwerty.key('t', IssueDetail.on_files_list_key_event('toggle_files_list'));
            // files list navugation
            $document.on('click', 'li:not(.disabled) a.go-to-previous-file', Ev.stop_event_decorate(IssueDetail.go_to_previous_file));
            $document.on('click', 'li:not(.disabled) a.go-to-next-file', Ev.stop_event_decorate(IssueDetail.go_to_next_file));
            $document.on('quicksearch.after', '.files-filter input.quicksearch', IssueDetail.on_files_filter_done);
            $document.on('click', 'li:not(.disabled) a.go-to-previous-file-comment', Ev.stop_event_decorate(IssueDetail.go_to_previous_file_comment));
            $document.on('click', 'li:not(.disabled) a.go-to-next-file-comment', Ev.stop_event_decorate(IssueDetail.go_to_next_file_comment));
            jwerty.key('p/k', IssueDetail.on_files_list_key_event('go_to_previous_file'));
            jwerty.key('n/j', IssueDetail.on_files_list_key_event('go_to_next_file'));
            jwerty.key('shift+p/shift+k', IssueDetail.on_files_list_key_event('go_to_previous_file_comment'));
            jwerty.key('shift+n/shift+j', IssueDetail.on_files_list_key_event('go_to_next_file_comment'));
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
            var $input, target, content, options, qs;
            $input = $(this);
            if (!$input.data('quicksearch')) {
                target = $input.data('target');
                if (!target) { return; }

                content = $input.data('content');

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
                if (content) {
                    options.selector = content;
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
    });
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
            $(this).parent().next('.email-hidden-reply').toggle();
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
    };
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

        display_issue: (function IssueEditor__display_issue (html, context) {
            var is_popup = context.$container.parents('.modal').length > 0;
            IssueDetail.display_issue(html, context.issue_ident, is_popup);
        }), // display_issue

        get_form_context: (function IssueEditor__get_form_context ($form) {
            var $container = $form.closest('.issue-container'),
            context = {
                issue_ident: IssueDetail.get_issue_ident($container),
                $form: $form,
                $container: $container
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

        /* CREATE COMMENT */
        on_comment_create_submit: (function IssueEditor__on_comment_create_submit (ev) {
            var $form = $(this),
                context = IssueEditor.handle_form($form, ev);
            if (context === false) { return false; }

            var $textarea = $form.find('textarea');

            if (!$textarea.val().trim()) {
                $textarea.after('<div class="alert alert-error">You must enter a comment</div>');
                $form.find('button').removeClass('loading');
                IssueEditor.enable_form($form);
                $textarea.focus();
                return false;
            }

            IssueEditor.post_form($form, context, IssueEditor.on_comment_create_submit_done,
                                                  IssueEditor.on_comment_create_submit_failed);
        }), // on_comment_create_submit

        on_comment_create_submit_done: (function IssueEditor__on_comment_create_submit_done (data) {
            this.$form.find('button').removeClass('loading');
            IssueEditor.display_issue(data, this);
        }), // on_comment_create_submit_done

        on_comment_create_submit_failed: (function IssueEditor__on_comment_create_submit_failed () {
            IssueEditor.enable_form(this.$form);
            this.$form.find('.alert').remove();
            var $textarea = this.$form.find('textarea');
            $textarea.after('<div class="alert alert-error">We were unable to post your comment</div>');
            this.$form.find('button').removeClass('loading');
            $textarea.focus();
        }), // on_comment_create_submit_failed

        // CREATE THE PR-COMMENT FORM
        on_comment_create_placeholder_click: (function IssueEditor__on_comment_create_placeholder_click (ev) {
            var $placeholder = $(this).parent(),
                $comment_box = IssueEditor.create_comment_form_from_template($placeholder.closest('.issue-container'));
            $comment_box.$form.prepend('<input type="hidden" name="entry_point_id" value="' + $placeholder.data('entry-point-id') + '"/>')
            $placeholder.after($comment_box.$node);
            $placeholder.hide();
            $comment_box.$textarea.focus();
        }), // on_comment_create_placeholder_click

        create_comment_form_from_template: (function IssueEditor__create_comment_form_from_template ($issue) {
            var $template = $issue.find('.comment-create-container'),
                $node = $template.clone(),
                $form = $node.find('form'),
                $textarea;
            $node.removeClass('comment-create-container');
            $form.attr('action', $form.data('pr-url'));
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
                $entry_point = $tr.closest('.code-diff').next('.pr-comments');
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
            $box = $issue.find('.pr-comments.template').clone().removeClass('template').removeAttr('style');
            $comment_box = IssueEditor.create_comment_form_from_template($issue);
            $comment_box.$form.prepend('<input type="hidden" name="path" value="' + path + '"/>' +
                                       '<input type="hidden" name="sha" value="' + sha + '"/>' +
                                       '<input type="hidden" name="position" value="' + position + '"/>');
            $box.find('ul').append($comment_box.$node);
            $table.parent().after($box);
            $comment_box.$textarea.focus();

        }), // on_new_entry_point_click

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
            var field = $link.data('field'),
                $placeholder = $link.closest('article').find('.edit-place[data-field=' + field + ']'),
                method = 'on_issue_edit_' + field + '_ready';
            if (typeof IssueEditor[method] == 'undefined') {
                method = 'on_issue_edit_default_ready';
            }
            IssueEditor[method]($link, $placeholder, data);
        }), // on_issue_edit_field_ready

        on_issue_edit_default_ready: (function IssueEditor__on_issue_edit_default_ready ($link, $placeholder, data) {
            var $form = $(data);
            $link.remove();
            $placeholder.replaceWith($form);
            IssueEditor.focus_form($form, 50);
            return $form;
        }), // on_issue_edit_default_ready

        on_issue_edit_title_ready: (function IssueEditor__on_issue_edit_title_ready ($link, $placeholder, data) {
            var left = $placeholder.position().left, $form;
            $placeholder.parent().after($placeholder);
            $form = IssueEditor.on_issue_edit_default_ready($link, $placeholder, data);
            $form.css('left', left + 'px');
        }), // on_issue_edit_title_ready

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
                    url: static_base_url + 'front/css/select.2.css',
                    dataType: 'text',
                    cache: true,
                    success: function(data) {
                        $('<style>').attr('type', 'text/css').text(data).appendTo('head');
                        on_one_done();
                    }
                });
                $.ajax({
                    url: static_base_url + 'front/js/select.2.js',
                    dataType: 'script',
                    cache: true,
                    success: on_one_done
                });
            } else {
                callback();
            }
        }), // load_select2

        on_issue_edit_milestone_ready: (function IssueEditor__on_issue_edit_milestone_ready ($link, $placeholder, data) {
            var callback = function() {
                var $form = IssueEditor.on_issue_edit_default_ready($link, $placeholder, data),
                    $select = $form.find('select'),
                    milestones_data = $select.data('milestones'),
                    format = function(state, include_title) {
                        if (state.children) {
                            return state.text.charAt(0).toUpperCase() + state.text.substring(1) + ' milestones';
                        }
                        var data = milestones_data[state.id];
                        if (data) {
                            var result = '<i class="icon-tasks text-' + data.state + '"> </i> <strong>' + (data.title.length > 25 ? data.title.substring(0, 20) + '…' : data.title);
                            if (include_title) {
                                var title = data.state.charAt(0).toUpperCase() + data.state.substring(1) + ' milestone';
                                if (data.state == 'open' && data.due_on) {
                                    title += ', due on ' + data.due_on;
                                }
                                result = '<div title="' + title + '">' + result + '</div>';
                            }
                            return result;
                        } else {
                            return '<i class="icon-tasks"> </i> No milestone';
                        }
                    };
                $select.select2({
                    formatSelection: function(state) { return format(state, false); },
                    formatResult:  function(state) { return format(state, true); },
                    escapeMarkup: function(m) { return m; },
                    dropdownCssClass: 'select2-milestone'
                });
                $form.closest('.modal').removeAttr('tabindex');  // tabindex set to -1 bugs select2
            }
            IssueEditor.load_select2(callback);
        }), // on_issue_edit_milestone_ready

        on_issue_edit_assignee_ready: (function IssueEditor__on_issue_edit_assignee_ready ($link, $placeholder, data) {
            var callback = function() {
                var $form = IssueEditor.on_issue_edit_default_ready($link, $placeholder, data),
                    $select = $form.find('select'),
                    collaborators_data = $select.data('collaborators'),
                    format = function(state, include_icon) {
                        var data = collaborators_data[state.id];
                        if (data) {
                            var avatar_url = data.avatar_url || default_avatar;
                            result = '<img class="avatar-tiny img-circle" src="' + avatar_url + '" /> <strong>' + (data.username.length > 25 ? data.username.substring(0, 20) + '…' : data.username);
                        } else {
                            result = 'No one assigned';
                        }
                        if (include_icon) {
                            result = '<i class="icon-hand-right"> </i> ' + result;
                        }
                        return result;
                    };
                $select.select2({
                    formatSelection: function(state) { return format(state, true); },
                    formatResult:  function(state) { return format(state, false); },
                    escapeMarkup: function(m) { return m; },
                    dropdownCssClass: 'select2-assignee'
                });
                $form.closest('.modal').removeAttr('tabindex');  // tabindex set to -1 bugs select2
            }
            IssueEditor.load_select2(callback);
        }), // on_issue_edit_assignee_ready

        on_issue_edit_labels_ready: (function IssueEditor__on_issue_edit_labels_ready ($link, $placeholder, data) {
            var callback = function() {
                var $form = IssueEditor.on_issue_edit_default_ready($link, $placeholder, data),
                    $select = $form.find('select'),
                    labels_data = $select.data('labels'),
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
                    };
                $select.select2({
                    formatSelection: function(state) { return format(state, true); },
                    formatResult:  function(state) { return format(state, false); },
                    escapeMarkup: function(m) { return m; },
                    dropdownCssClass: 'select2-labels',
                    closeOnSelect: false
                }).on('select2-focus', function() {
                    $select.select2('open');
                });
                $form.closest('.modal').removeAttr('tabindex');  // tabindex set to -1 bugs select2
            }
            IssueEditor.load_select2(callback);
        }), // on_issue_edit_labels_ready

        on_issue_edit_field_cancel_click: (function IssueEditor__on_issue_edit_field_cancel_click (ev) {
            var $btn = $(this),
                $form = $btn.closest('form');
            if ($form.data('disabled')) { return false; }
            IssueEditor.disable_form($form);
            $btn.addClass('loading');
            var $container = $form.closest('.issue-container');
            var issue_ident = IssueDetail.get_issue_ident($container);
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


        init: (function IssueEditor__init () {
            $document.on('submit', '.issue-edit-state-form', IssueEditor.on_state_submit);

            $document.on('click', 'a.issue-edit-btn', Ev.stop_event_decorate(IssueEditor.on_issue_edit_field_click));
            $document.on('click', 'form.issue-edit-field button.btn-cancel', Ev.stop_event_decorate(IssueEditor.on_issue_edit_field_cancel_click));
            $document.on('submit', 'form.issue-edit-field', Ev.stop_event_decorate(IssueEditor.on_issue_edit_field_submit));

            $document.on('submit', '.comment-create-form', IssueEditor.on_comment_create_submit);
            $document.on('click', '.comment-create-placeholder button', IssueEditor.on_comment_create_placeholder_click);

            $document.on('click', 'td.code span.label', IssueEditor.on_new_entry_point_click);
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
            issue_link: '.box-section > h3 > a',
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
            find_empty: ':not(:has(.chat-box > li))'
        },

        on_issue_link_click: (function Activity__on_issue_link_click () {
            var $link = $(this),
                $block = $link.closest('.box-section'),
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

        get_entry_score: (function Activity__get_entry_score ($entry) {
            return $entry.data('score');
        }), // get_entry_score

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

        add_loaded_entries: (function Activity__add_loaded_entries($main_node, data, limits, $placeholder, callback) {
            var $container = $('<div />'),
                mode = $main_node.data('mode'),
                idents = {}, $check, $same_score_entries,
                $entries, $entry, is_min, is_max;

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

            // remove old "recent" marks
            $main_node.find(Activity.selectors.containers[mode] + '.recent').removeClass('recent');

            // insert data if there is still
            if ($container.find(Activity.selectors.entries.all).length) {
                $entries = $container.children().replaceAll($placeholder);
                setTimeout(function() { $entries.addClass('recent'); }, 10);
                if (callback) { callback('ok'); }
            } else {
                Activity.update_placeholder($placeholder, 'nothing', callback);
            }
        }), // add_loaded_entries

        placeholders: {
            nothing: {
                message: 'Nothing new',
                icon: 'icon-eye-close',
                delay: 1000
            },
            error: {
                message: 'Error while loading',
                icon: 'icon-remove-sign',
                delay: 3000
            },
            loading: {
                message: 'Loading',
                icon: 'icon-spinner icon-spin',
                delay: -1
            },
            more: {
                message: 'Load more',
                icon: 'icon-plus',
                delay: -1,
                classes: 'box-footer',
                link: '#'
            },
            missing: {
                message: 'Load missing',
                icon: 'icon-plus',
                delay: -1,
                classes: 'more box-footer',
                link: '#'
            }
        }, // placeholders

        update_placeholder: (function Activity__update_placeholder($placeholder, type, callback, replace_type) {
            var params = Activity.placeholders[type];
            $placeholder[0].className = 'placeholder visible ' + type + (params.classes ? ' ' + params.classes : '');  // use className to remove all previous
            var html = '<i class="' + params.icon + '"> </i> ' + params.message;
            if (params.link) {
                html = '<a href="' + params.link + '">' + html + '</a>';
            }
            $placeholder.html(html);
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

        load_data: (function Activity__load_data($main_node, limits, $placeholder, callback, retry_placeholder) {
            var data = { partial: 1};

            if (limits.min) { data.min = limits.min; }
            if (limits.max) { data.max = limits.max; }

            $.ajax({
                url: $main_node.data('url'),
                data: data,
                dataType: 'html',
                success: function(data) {
                    Activity.add_loaded_entries($main_node, data, limits, $placeholder, callback);
                },
                error: function() {
                    Activity.update_placeholder($placeholder, 'error', callback, retry_placeholder);
                }
            });

        }), // load_data

        on_refresh_button_click: (function Activity__on_refresh_button_click () {
            var $this = $(this), $main_node, mode, $placeholder, $first_entry, score;

            if ($this.hasClass('disabled')) { return false; }
            $this.addClass('disabled');

            $main_node = Activity.get_main_node($this);
            $main_node.children('.box-content').scrollTop(1).scrollTop(0);

            $placeholder = $('<div class="placeholder loading"><i class="' + Activity.placeholders.loading.icon + '"> </i> ' + Activity.placeholders.loading.message + '</div>');
            mode = $main_node.data('mode');
            $main_node.find(Activity.selectors.containers[mode]).first().before($placeholder);
            setTimeout(function() { $placeholder.addClass('visible'); }, 10);

            $first_entry = $main_node.find(Activity.selectors.entries.first);
            score = $first_entry.data('score');

            Activity.load_data($main_node, {min: score}, $placeholder, function(is_success) {
                $this.removeClass('disabled');
            });

            return false;
        }), // on_refresh_button_click

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

            Activity.load_data($main_node, limits, $placeholder, null, is_missing_btn ? 'missing' : 'more');

            return false;
        }), // on_more_button_click

        init_feeds: (function Activity__init_feeds () {
            setInterval(function() {
                var $feeds = $(Activity.selectors.main);
                for (var i = 0; i < $feeds.length; i++) {
                    replace_time_ago($feeds[i]);
                }
            }, 60000);
        }), // init_feeds

        init_events: (function Activity__init_events () {
            $document.on('click', Activity.selectors.main + ' ' + Activity.selectors.issue_link, Ev.stop_event_decorate(Activity.on_issue_link_click));
            $document.on('click', Activity.selectors.main + ' ' + Activity.selectors.buttons.refresh, Ev.stop_event_decorate(Activity.on_refresh_button_click));
            $document.on('click', Activity.selectors.main + ' ' + Activity.selectors.buttons.more, Ev.stop_event_decorate(Activity.on_more_button_click));
        }), // init_events

        init: (function Activity__init () {
            Activity.init_feeds();
            Activity.init_events();
        }) // init
    }; // Activity
    Activity.init();

});

