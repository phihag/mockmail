function rawHeader_toggle() {
	var link = $(this);
	var emailHeader = link.parent().parent().children('.header');
	var rawDisplay = emailHeader.children('.header_raw');
	if (rawDisplay.length > 0) {
		rawDisplay.remove();
		emailHeader.children('.header_parsed').show();
		link.text('Show raw header');
	} else {
		var rawDisplay = $('<div class="raw header_raw"></div>');
		rawDisplay.text(emailHeader.attr('data-rawheader'));
		emailHeader.append(rawDisplay);
		emailHeader.children('.header_parsed').hide();
		link.text('Show parsed header');
	}
}

function rawBody_toggle() {
	var link = $(this);
	var emailBody = link.parent().parent().children('.body');
	var rawDisplay = emailBody.children('.body_raw');
	if (rawDisplay.length > 0) {
		rawDisplay.remove();
		emailBody.children('.body_parsed').show();
		link.text('Show raw body');
	} else {
		var rawDisplay = $('<div class="raw body_raw"></div>');
		rawDisplay.text(emailBody.attr('data-rawbody'));
		emailBody.append(rawDisplay);
		emailBody.children('.body_parsed').hide();
		link.text('Show parsed body');
	}
}

$(function() {
	$('.email').each(function (i, email_container) {
		var commandlinks = $('<div class="commandlinks"></div>');
		$(email_container).prepend(commandlinks);

		var rb_link = $('<a href="#"></a>');
		rb_link.text('Show raw body');
		rb_link.click(rawBody_toggle);
		$(commandlinks).prepend(rb_link);

		var rh_link = $('<a href="#"></a>');
		rh_link.text('Show raw header');
		rh_link.click(rawHeader_toggle);
		$(commandlinks).prepend(rh_link);
	});
});