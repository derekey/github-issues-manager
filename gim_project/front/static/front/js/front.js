$().ready(function() {

    var $document = $(document);

    var Ev = {
        stop_event_decorate: (function stop_event_decorate(callback) {
            /* Return a function to use as a callback for an event
               Call the callback and if it returns false (strictly), the
               event propagation is stopped
            */
            var decorator = function(e) {
                if (e.isPropagationStopped()) { return false; }
                if (callback(e) === false) {
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
        }) // charcode
    };


    var IssuesListIssue = (function IssuesListIssue__constructor (node, issues_list_group) {
        this.group = issues_list_group;

        this.node = node;
        this.node.IssuesListIssue = this;
        this.$node = $(node);
        this.$link = this.$node.find(IssuesListIssue.link_selector);

        this.number = this.$node.data('issue-number');
    }); // IssuesListIssue__constructor

    IssuesListIssue.selector = '.issue-item';
    IssuesListIssue.link_selector = '.issue-link';

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
    IssuesListIssue.set_urls = (function IssuesListIssue_set_urls () {
        $(IssuesListIssue.selector + ' ' + IssuesListIssue.link_selector).each(function() {
            var parts = this.href.split('#');
            this.href = parts[0] + location.search + '#' + parts[1];
        });
    }); // IssuesListIssue_set_urls

    IssuesListIssue.prototype.on_click = (function IssuesListIssue__on_click (e) {
        this.set_current(true);
        return false; // stop event propagation
    }); // IssuesListIssue__on_click

    IssuesListIssue.prototype.unset_current = (function IssuesListIssue__unset_current () {
        this.group.current_issue = null;
        this.$node.removeClass('active');
    }); // IssuesListIssue__unset_current

    IssuesListIssue.prototype.set_current = (function IssuesListIssue__set_current (propagate) {
        this.get_html_and_display();
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

    IssuesListIssue.prototype.get_html_and_display = (function IssuesListIssue__get_html_and_display (url, in_popup) {
        if (!IssuesList.can_display_issue_html(this.number, in_popup)) {
            return;
        }
        if (!url) { url = this.$link.attr('href'); }
        $.ajax({
            url: url,
            success: in_popup ? this.display_html_in_popup : this.display_html,
            error: in_popup ? this.error_getting_html_in_popup: this.error_getting_html,
            context: this
        });
    }); // IssuesListIssue__get_html_and_display

    IssuesListIssue.prototype.display_html = (function IssuesListIssue__display_html (html) {
        IssuesList.display_issue_html(html, this.number, false);
    }); // IssuesListIssue__display_html

    IssuesListIssue.prototype.display_html_in_popup = (function IssuesListIssue__display_html_in_popup (html) {
        IssuesList.display_issue_html(html, this.number, true);
    }); // IssuesListIssue__display_html_in_popup

    IssuesListIssue.prototype.error_getting_html = (function IssuesListIssue__error_getting_html (jqXHR) {
        IssuesList.clear_issue_html('error ' + jqXHR.status, false);
    }); // IssuesListIssue__error_getting_html

    IssuesListIssue.prototype.error_getting_html_in_popup = (function IssuesListIssue__error_getting_html_in_popup (jqXHR) {
        alert('error ' + jqXHR.status);
    }); // IssuesListIssue__error_getting_html_in_popup

    IssuesListIssue.open_issue = (function IssuesListIssue_open_issue (number, in_popup) {
        var issue = IssuesList.get_issue_by_number(number);
        if (issue) {
            if (in_popup) {
                issue.get_html_and_display(null, true);
            } else {
                issue.set_current(true);
            }
        } else {
            var url = IssueByNumber.$input.data('base-url') + number + '/';
            issue = new IssuesListIssue({}, null);
            issue.number = number;
            issue.get_html_and_display(url, in_popup);
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
        IssuesList.clear_issue_html();
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
                    group.$issues_node.off('shown', on_shown);
                    on_shown_callback();
                };
            this.$issues_node.on('shown', on_shown);
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
        $document.on('show', IssuesListGroup.issues_list_selector, IssuesListGroup.on_group_node_event('on_show'));
        $document.on('hide', IssuesListGroup.issues_list_selector, IssuesListGroup.on_group_node_event('on_hide'));
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

    IssuesListGroup.prototype.get_issue_by_number = (function IssuesListGroup__get_issue_by_number(number) {
        var issue = null;
        for (var i = 0; i < this.issues.length; i++) {
            if (this.issues[i].number == number) {
                issue = this.issues[i];
                break;
            }
        }
        return issue;
    }); // IssuesListGroup__get_issue_by_number

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
    IssuesList.modal_window = $('#modal-issue-view');
    IssuesList.modal_window_issue_container = IssuesList.modal_window.find('.modal-body > .issue');
    IssuesList.issue_container = $('#main-issue-container');
    IssuesList.all = [];
    IssuesList.current = null;

    IssuesList.prototype.unset_current = (function IssuesList__unset_current () {
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
        IssuesListIssue.set_urls();
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
        jwerty.key('s', IssuesList.on_current_list_key_event('focus_search_input'));
        jwerty.key('ctrl+u', IssuesList.on_current_list_key_event('clear_search_input'));
        jwerty.key('d', Ev.key_decorate(IssuesList.toggle_details));
        for (var i = 0; i < IssuesList.all.length; i++) {
            var issues_list = IssuesList.all[i];
            if (issues_list.$search_input.length) {
                issues_list.$search_input.on('quicksearch.after', $.proxy(issues_list.on_filter_done, issues_list));
                issues_list.$search_input.on('keydown', jwerty.event('↑', issues_list.go_to_previous_item, issues_list));
                issues_list.$search_input.on('keydown', jwerty.event('↓', issues_list.go_to_next_item, issues_list));
            }
        }
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

    IssuesList.get_issue_html_container = (function IssuesList_get_issue_html_container (in_popup) {
        var panel = {
            $window: null,
            $node: IssuesList.issue_container,
            after: null
        }, popup = {
            $window: IssuesList.modal_window,
            $node: IssuesList.modal_window_issue_container,
            after: function($node) {  // TODO: move it in its own function
                $node.find('.issue-nav').append('<button type="button" class="close" data-dismiss="modal" title="Close" aria-hidden="true">&times;</button>');
            }
        };
        return (in_popup || !IssuesList.issue_container.length) ? popup : panel;
    }); // IssuesList_get_issue_html_container

    IssuesList.can_display_issue_html = (function IssuesList_can_display_issue_html (issue_number, in_popup) {
        var container = IssuesList.get_issue_html_container(in_popup);
        if (!in_popup && container.$node.data('issue-number') == issue_number) { return false; }
        container.$node.data('issue-number', issue_number);
        return true;
    }); // IssuesList_can_display_issue_html

    IssuesList.display_issue_html = (function IssuesList_display_issue_html (html, issue_number, in_popup) {
        var container = IssuesList.get_issue_html_container(in_popup);
        if (container.$node.data('issue-number') != issue_number) { return; }
        container.$node.html(html);
        if (container.after) {
            container.after(container.$node);
        }
        MarkdownManager.update_links();
        container.$node.scrollTop(0);
        if (container.$window) {
            container.$window.modal("show");
        }
    }); // IssuesList_display_issue_html

    IssuesList.clear_issue_html = (function IssuesList_clear_issue_html (code, in_popup) {
        var container = IssuesList.get_issue_html_container(in_popup);
        container.$node.data('issue-number', 0);
        container.$node.html('<p class="empty-area">' + (code ? code + ' :(' : '...') + '</p>');
    }); // IssuesList_clear_issue_html

    IssuesList.toggle_details = (function IssuesList_toggle_details () {
        for (var i = 0; i < IssuesList.all.length; i++) {
            var list = IssuesList.all[i];
            list.$node.toggleClass('without-details');
        }
        return false; // stop event propagation
    }); // IssuesList_toggle_details

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

    IssuesList.get_issue_by_number = (function IssuesList_get_issue_by_number(number) {
        var issue = null;
        for (var i = 0; i < IssuesList.all.length; i++) {
            issue = IssuesList.all[i].get_issue_by_number(number);
            if (issue) { break; }
        }
        return issue;
    }); // IssuesList_get_issue_by_number

    IssuesList.prototype.get_issue_by_number = (function IssuesList__get_issue_by_number(number) {
        var issue = null;
        for (var i = 0; i < this.groups.length; i++) {
            issue = this.groups[i].get_issue_by_number(number);
            if (issue) { break; }
        }
        return issue;
    }); // IssuesList__get_issue_by_number

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
            IssueByNumber.$input.focus();
            IssueByNumber.$input.prop('placeholder', "Type an issue number");

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
                IssueByNumber.open_issue(number);
            } else {
                IssueByNumber.$input.prop('placeholder', "Type a correct issue number");
            IssueByNumber.$input.focus();
            }
            return false; // stop event propagation
        }), // IssueByNumber_on_submit
        open_issue: (function IssueByNumber_open_issue (number) {
            IssuesListIssue.open_issue(number);
        }), // IssueByNumber_open_issue
        init_events: (function IssueByNumber_init_events () {
            if (!IssueByNumber.$window.length) { return; }
            $document.on('keypress', Ev.key_decorate(Ev.charcode(35, IssueByNumber.open)));  // 35 = #
            jwerty.key('i', Ev.key_decorate(IssueByNumber.open));
            IssueByNumber.$window.on('show', IssueByNumber.on_show);
            IssueByNumber.$window.on('shown', IssueByNumber.on_shown);
            IssueByNumber.$form.on('submit', Ev.stop_event_decorate(IssueByNumber.on_submit));
        }) // IssueByNumber_init_events
    }; // IssueByNumber

    IssueByNumber.init_events();

    var on_resize_issue_click = (function on_resize_issue_click(e) {
        var $modal = $('.modal.in');
        if ($modal.length) {
            $modal.toggleClass('full-screen');
        } else {
            $('body').toggleClass('big-issue');
        }
        return false; // stop event propagation
    }); // on_resize_issue_click

    $document.on('hidden', '.modal', function () {
        $(this).removeClass('full-screen');
    });

    var on_help = (function on_help(e) {
        $('#show-shortcuts').click();
        return false; // stop event propagation
    }); // on_help

    // keyboard events
    jwerty.key('f', Ev.key_decorate(on_resize_issue_click));
    $document.on('click', '.resize-issue', Ev.stop_event_decorate(on_resize_issue_click));
    $document.on('click', '#toggle-issues-details', Ev.stop_event_decorate_dropdown(IssuesList.toggle_details));
    $document.on('click', '#close-all-groups', Ev.stop_event_decorate_dropdown(IssuesList.close_all_groups));
    $document.on('click', '#open-all-groups', Ev.stop_event_decorate_dropdown(IssuesList.open_all_groups));

    if ($('#show-shortcuts').length) {
        $document.on('keypress', Ev.key_decorate(Ev.charcode(63, on_help)));  // 63 = ?
    }


    // select the issue given in the url's hash, or an active one in the html,
    // or the first item of the current list
    if (IssuesList.all.length) {
        IssuesList.all[0].set_current();
        var issue_to_select = null;
        if (location.hash && /^#issue\-\d+$/.test(location.hash)) {
            issue_to_select = $(location.hash);
            if (issue_to_select.length && issue_to_select[0].IssuesListIssue) {
                issue_to_select[0].IssuesListIssue.set_current(true);
            } else {
                issue_to_select = null;
            }
        } else {
            issue_to_select = $(IssuesListIssue.selector + '.active');
            if (issue_to_select.length) {
                issue_to_select.removeClass('active');
                issue_to_select[0].IssuesListIssue.set_current(true);
            } else {
                issue_to_select = null;
            }
        }
        if (!issue_to_select) {
            IssuesList.current.go_to_next_item();
        }
    }

    var activate_quicksearches = (function activate_quicksearches () {
        $('input.quicksearch').each(function() {
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
    activate_quicksearches();

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
        re: null,
        toggle_email_reply: function() {
            $(this).parent().next('.email-hidden-reply').toggle();
            return false;
        }, // toggle_email_reply
        activate_email_reply_toggle: function() {
            $document.on('click', '.email-hidden-toggle a', MarkdownManager.toggle_email_reply);
        }, // activate_email_reply_toggle
        update_link: function() {
            var $link = $(this);
            $link.attr('target', '_blank');
            if (!MarkdownManager.re) {
                MarkdownManager.re = new RegExp('https?://github.com/' + $('body').data('repository') + '/(?:issue|pull)s?/(\\d+)');
            }
            var matches = this.href.match(MarkdownManager.re);
            if (matches) {
                $link.data('issue-number', matches[1])
                     .addClass('issue-link');
            }
        }, // update_link
        update_links: function() {
            $('.issue').find('.issue-body, .issue-comment .content').find('a')
                .each(MarkdownManager.update_link);
        }, // update_links
        handle_issue_link: function() {
            var $link = $(this),
                issue_number = $link.data('issue-number');
            if (issue_number) {
                IssuesListIssue.open_issue(issue_number, true);
                return false;
            }
        }, // handle_issue_link
        handle_issue_links: function() {
            $document.on('click', '.issue a.issue-link', MarkdownManager.handle_issue_link);
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
                    $('body > header:first-of-type').after($new_messages);
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

        on_state_submit: (function IssueEditor__on_state_submit (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            var $form = $(this),
                issue_number = $form.data('issue-number');
            $form.find('button').addClass('loading');
            $.post($form.attr('action'), $form.serialize())
                .done($.proxy(IssueEditor.on_state_submit_done, { issue_number: issue_number }))
                .fail($.proxy(IssueEditor.on_state_submit_failed, { issue_number: issue_number }));
        }), // on_state_submit

        on_state_submit_done: (function IssueEditor__on_state_submit_done (data) {
            IssuesList.display_issue_html(data, this.issue_number);
        }), // on_state_submit_done

        on_state_submit_failed: (function IssueEditor__on_state_submit_failed () {
            $form.find('button').removeClass('loading');
            alert('A problem prevented us to do your action !');
        }), // on_state_submit_failed

        init: (function IssueEditor__init () {
            $document.on('submit', '.issue-edit-state-form', IssueEditor.on_state_submit);
        }) // init
    }; // IssueEditor
    IssueEditor.init();

});
