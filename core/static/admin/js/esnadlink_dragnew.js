(function () {
    if (!window.django || !window.django.jQuery) return;
    const $ = window.django.jQuery;

    const TBODY_SELECTOR = 'div.inline-group table tbody';

    function nextOrder($tbody) {
        let max = 0;
        $tbody.find('tr').each(function () {
            const $row = $(this);
            const reorderVal = parseInt($row.find('input._reorder_').val(), 10);
            const orderVal = parseInt($row.find('input[name$="-order"]').val(), 10);
            const v = !isNaN(reorderVal) ? reorderVal : orderVal;
            if (!isNaN(v) && v > max) max = v;
        });
        return max + 1;
    }

    function renumberAll($tbody) {
        let idx = 0;
        $tbody.find('tr').each(function () {
            const $row = $(this);
            if ($row.find('input[name$="-DELETE"]').is(':checked')) return;
            idx += 1;
            const $reorder = $row.find('input._reorder_');
            const $order = $row.find('input[name$="-order"]');
            if ($reorder.length) $reorder.val(idx);
            if ($order.length) $order.val(idx);
        });
    }

    $(document).on('formset:added', function (event, $row, formsetName) {
        const $newRow = $row && $row.jquery ? $row : $(event.target);
        const $tbody = $newRow.closest('tbody');
        if (!$tbody.length) return;
        const $order = $newRow.find('input[name$="-order"]');
        if ($order.length && !$order.val()) $order.val(nextOrder($tbody));
    });

    $(document).on('sortend dragend drop', TBODY_SELECTOR, function () {
        renumberAll($(this));
    });
})();
