(function($) {
  $(document).ready(function() {
    const modal   = $('#convertModal');
    const close   = $('.leads-close');
    const form    = $('#convertForm');
    const phoneIn = $('#modalPhone');
    const interestIdSpan = $('#modalInterestId');

    // 1) On clicking any Convert button…
    $('.convert-to-lead-btn, a.button').on('click', function(e) {
      e.preventDefault();
      const url = $(this).attr('href');
      // Extract interest ID from URL (/…/convert-to-lead/)
      const interestId = url.split('/').slice(-2, -1)[0];

      // Prefill phone & interestId
      interestIdSpan.text(interestId);
      // We know phone is in the same row
      const phone = $(this).closest('tr').find('td.field-phone').text().trim();
      phoneIn.val(phone);

      // Set the form action to this URL
      form.attr('action', url);

      // Show the modal
      modal.show();
    });

    // 2) Close the modal
    close.on('click', function() {
      modal.hide();
    });
    $(window).on('click', function(e) {
      if ($(e.target).is(modal)) modal.hide();
    });

    // 3) Submit via AJAX
    form.on('submit', function(e) {
      e.preventDefault();
      const actionUrl = form.attr('action');
      $.post(actionUrl, form.serialize())
       .done(function() {
         window.location.reload();
       })
       .fail(function(xhr) {
         alert('Error: ' + xhr.responseText);
       });
    });
  });
})(django.jQuery);