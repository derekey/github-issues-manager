var replace_time_ago = (function () {
    "use strict";
    var origin = new Date(document.body.getAttribute('data-base-datetime')),
        content_method = ('textContent' in document.body) ? 'textContent' : 'innerHTML',
        halfstr = "½",
        dict = {
            'short': {
                'mns': ' mn',
                'hs': 'h',
                'd': '1 d',
                'ds': ' d',
                'w': '1 w',
                'ws': ' w',
                'mo': '1 mo',
                'mos': ' mo',
                'y': '1 y',
                'ys': ' y'
            },
            'long': {
                'mns': ' min ago',
                'hs': 'h ago',
                'd': 'day ago',
                'ds': ' days ago',
                'w': 'week ago',
                'ws': ' weeks ago',
                'mo': 'month ago',
                'mos': ' months ago',
                'y': 'year ago',
                'ys': ' years ago'
            }
        };

    function divmod(x, y) {
        return [(x - x % y) / y, x % y];
    }

    function ago(delta, is_short) {
        // based on https://github.com/twidi/pytimeago, to share same return result
        var delta, fmt, mins, hours, half, days, wdays, weeks, months, years,
            hours_and_mins, days_and_hours, weeks_and_wdays, months_and_days;

        fmt = dict[is_short ? 'short' : 'long'];

        // now
        if (delta === 0) {
            return 'now';
        }

        // < 1 hour
        mins = Math.round(delta / 60);
        if (mins < 60) {
            return mins + fmt.mns;
        }

        // < 1 day
        hours_and_mins =  divmod(mins, 60);
        hours = hours_and_mins[0];
        mins =hours_and_mins[1];
        if (hours < 24) {
            // "half" is for 30 minutes in the middle of an hour
            half = (15 <= mins && mins <= 45) ? halfstr : '';
            return hours + half + fmt.hs;
        }

        //  < 7 days
        hours += Math.round(mins / 60);
        days_and_hours = divmod(hours, 24);
        days = days_and_hours[0];
        hours = days_and_hours[1];
        if (days === 1) {
            return fmt.d;
        }
        if (days < 7) {
            half = (6 <= hours && hours <= 18) ? halfstr : '';
            return days + half + fmt.ds;
        }

        // < 4 weeks
        days += Math.round(hours / 24);
        if (days < 9) {
            return fmt.w;
        }
        weeks_and_wdays = divmod(days, 7);
        weeks = weeks_and_wdays[0];
        wdays = weeks_and_wdays[1];
        if (2 <= wdays && wdays <= 4) {
            half = halfstr;
        } else {
            half = '';
            if (wdays > 4) {
                weeks += 1;
            }
        }
        if (weeks < 4) { // So we don't get 4 weeks
            return weeks + half + fmt.ws;
        }

        // < year
        if (days < 35) {
            return fmt.mo;
        }
        months_and_days = divmod(days, 30);
        months = months_and_days[0];
        days = months_and_days[1];
        if (10 <= days && days <= 20) {
            half = halfstr;
        } else {
            half = '';
            if (days > 20) {
                months += 1;
            }
        }
        if (months < 12) {
            return months + half + fmt.mos;
        }

        // Don't go further
        years = Math.round(months / 12);
        if (years === 1) {
            return fmt.y;
        }
        return years + fmt.ys;

    } // ago

    function replace(node) {
        var date_str, date, delta, is_short;

        date_str = node.getAttribute('data-datetime');
        if (!date_str) { return; }

        date = new Date(date_str);
        delta = (origin - date) / 1000;
        if (isNaN(delta)) { return; }

        is_short = (node.className.indexOf('ago-short') >= 0);
        node[content_method] = ago(delta, is_short);
    }

    function update_ago(node) {
        var nodes = Array.prototype.slice.call((node || document).getElementsByClassName('ago')), i;
        for (i = 0; i < nodes.length; i++) {
            replace(nodes[i]);
        }
    }

    return update_ago;

})();
