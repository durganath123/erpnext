window.zoom_item_image = function(parent, child, attr) {
    var $modal = $("#zoom_modal");
    if (!$modal || !$modal.legnth) {
    	$modal = $(`<div id="zoom_modal" class="modal zoom_modal">
			<span class="close">&times;</span><img class="modal-img-content" id="zoom_image"></div>`);
    	$("body").append($modal);

    	$(document).on('keydown', function(e) {
			if (e.keyCode === 27) {
				$modal.css('display', 'none');
			}
		});
		$(".close", $modal).click(function() {
			$modal.css('display', 'none');
    	});
		$modal.click(function (e) {
			if ($(e.target).is('.zoom_modal')) {
				$modal.css('display', 'none');
			}
		});
	}

    var $modalImg = $("#zoom_image", $modal);

    $(parent).on('click', child, function() {
        var pro_img = $(this).attr(attr);
        if (pro_img) {
            $modal.css('display', 'block');
            $modalImg.attr('src', pro_img);
        }
    });
};