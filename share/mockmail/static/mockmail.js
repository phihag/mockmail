function rawHeader_toggle() {
	var link = $(this);
	var emailHeader = link.parent();
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

$(function() {
	$('.email>.header').each(function (i, header) {
		var link = $('<a href="#" class="commandlink"></a>');
		link.text('Show raw header');
		link.click(rawHeader_toggle);
		$(header).prepend(link);
	});
});